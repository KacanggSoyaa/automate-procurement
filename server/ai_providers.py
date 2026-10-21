"""Provider-agnostic AI clients shared by classification and supplier search.

One adapter per vendor (Google Gemini, OpenAI, Anthropic) exposes the same
two operations:

- ``generate_json``  – one structured (schema-validated) generation call
- ``search_json``    – one live web-search-grounded call that returns JSON

Each adapter encodes the shared text/image parts with its own SDK and turns
vendor-specific failures into the shared quota/transient error vocabulary so
callers can keep the existing retry + model-fallback loops.
"""
import base64
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from pydantic import BaseModel

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import anthropic
except ImportError:
    anthropic = None

PROVIDER_IDS = ("gemini", "openai", "anthropic")

_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".gif": "image/gif",
}


@dataclass(frozen=True)
class ProviderSpec:
    """Static description of one supported AI vendor."""

    id: str
    label: str
    env_key: str
    key_url: str
    package: str
    default_model: str
    models: tuple
    fallback_models: tuple
    search_timeout_ms: int = 120000

    @property
    def env_prefix(self) -> str:
        return self.env_key.rsplit("_API_KEY", 1)[0]

    @property
    def model_env(self) -> str:
        return f"{self.env_prefix}_MODEL"


PROVIDERS: Dict[str, ProviderSpec] = {
    spec.id: spec
    for spec in (
        ProviderSpec(
            id="gemini",
            label="Google Gemini",
            env_key="GEMINI_API_KEY",
            key_url="https://aistudio.google.com/apikey",
            package="google-genai",
            default_model="gemini-3.8-flash",
            models=("gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest", "gemini-3.1-flash-lite"),
            fallback_models=("gemini-3.5-flash", "gemini-flash-latest", "gemini-3.1-flash-lite"),
            search_timeout_ms=30000,
        ),
        ProviderSpec(
            id="openai",
            label="OpenAI",
            env_key="OPENAI_API_KEY",
            key_url="https://platform.openai.com/api-keys",
            package="openai",
            default_model="gpt-6-luna",
            models=("gpt-6-luna", "gpt-6-astra", "gpt-6.1-sol", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"),
            fallback_models=("gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-luna"),
        ),
        ProviderSpec(
            id="anthropic",
            label="Anthropic",
            env_key="ANTHROPIC_API_KEY",
            key_url="https://console.anthropic.com/settings/keys",
            package="anthropic",
            default_model="claude-sonnet-5-5",
            models=("claude-sonnet-5-5", "claude-sonnet-5", "claude-opus-5-5", "claude-sonnet-4-6"),
            fallback_models=("claude-sonnet-5", "claude-opus-5-5", "claude-sonnet-4-6"),
        ),
    )
}


class UnsupportedSearchError(RuntimeError):
    """The provider/model does not support the live web-search tool."""


def get_spec(provider: Optional[str]) -> ProviderSpec:
    """Return the spec for ``provider`` (env ``AI_PROVIDER`` else Gemini)."""
    pid = (provider or os.environ.get("AI_PROVIDER") or "gemini").strip().lower()
    if pid not in PROVIDERS:
        raise ValueError(f"Unknown AI provider '{provider}'. Choose one of: {', '.join(PROVIDER_IDS)}.")
    return PROVIDERS[pid]


def provider_label(provider: Optional[str]) -> str:
    return get_spec(provider).label


def resolve_key(provider: Optional[str], api_key: Optional[str] = None) -> Optional[str]:
    """The caller's own key when given, else the shared server env key."""
    spec = get_spec(provider)
    return (api_key or os.environ.get(spec.env_key) or "").strip() or None


def resolve_model(provider: Optional[str], model: Optional[str] = None) -> str:
    spec = get_spec(provider)
    return (model or os.environ.get(spec.model_env) or "").strip() or spec.default_model


def missing_key_error(spec: ProviderSpec) -> RuntimeError:
    return RuntimeError(
        f"{spec.env_key} is not set and no personal key is saved for your account. "
        f"Get a key from {spec.key_url} and add it in Settings, or set it as an "
        f"environment variable."
    )


# --------------------------------------------------------------------------- errors
_QUOTA_MARKERS = (
    "perday", "per-day", "per day", "current quota", "daily quota", "quota exceeded",
    "insufficient_quota", "insufficient quota", "credit balance", "usage limit",
    "exceeded your", "billing", "quota has been exceeded",
)
_TRANSIENT_MARKERS = (
    "503", "500", "502", "504", "429", "unavailable", "resource_exhausted",
    "overloaded", "rate limit", "rate_limit", "too many requests", "timeout",
    "timed out", "temporarily", "connection", "capacity", "internal error",
    "internal server error", "please try again",
)
_UNSUPPORTED_SEARCH_MARKERS = (
    "web_search", "web search", "search tool", "grounding", "not supported",
    "unsupported", "not allowed", "not enabled", "disabled", "invalid",
)


def is_quota_error(msg: str) -> bool:
    """Daily/billing quota exhaustion: skip straight to the next model."""
    low = (msg or "").lower()
    return any(m in low for m in _QUOTA_MARKERS)


def is_transient_error(msg: str) -> bool:
    """Worth retrying the same model after a short backoff."""
    low = (msg or "").lower()
    return any(m in low for m in _TRANSIENT_MARKERS)


def is_unsupported_search(msg: str) -> bool:
    """The model/provider rejects the live search tool (try another model)."""
    low = (msg or "").lower()
    return any(m in low for m in _UNSUPPORTED_SEARCH_MARKERS)


# --------------------------------------------------------------------------- JSON
def extract_json(text: str, schema):
    """Parse ``text`` into ``schema``, tolerating fences and surrounding prose.

    Tries the raw string first, then fenced code blocks, then the first
    balanced ``{…}`` region. Raises ValueError when nothing validates.
    """
    candidates = [text.strip()] if text else []
    candidates += [b.strip() for b in re.findall(r"```(?:json)?\s*(.*?)```", text or "", re.S)]
    start = (text or "").find("{")
    if start >= 0:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : i + 1])
                    break
    for cand in candidates:
        if not cand:
            continue
        try:
            return schema.model_validate_json(cand)
        except Exception:
            try:
                return schema.model_validate(json.loads(cand))
            except Exception:
                continue
    raise ValueError("The model response did not contain valid JSON for the expected schema.")


class ImagePart:
    """An image read from disk, encoded per provider at call time."""

    def __init__(self, path: str):
        self.path = path
        self.data = Path(path).read_bytes()
        self.mime = _MIME_BY_EXT.get(Path(path).suffix.lower(), "image/png")


TextOrImage = Union[str, ImagePart]


def _data_uri(part: ImagePart) -> str:
    return f"data:{part.mime};base64,{base64.b64encode(part.data).decode('ascii')}"


class ProviderClient:
    """One vendor SDK client with a shared generate/search interface.

    The model used for a call can be overridden per call so a fallback chain
    can reuse a single client instance.
    """

    def __init__(self, provider: Optional[str] = None, api_key: Optional[str] = None,
                 model: Optional[str] = None, timeout_ms: Optional[int] = None):
        self.spec = get_spec(provider)
        self.provider = self.spec.id
        self._api_key_override = (api_key or "").strip() or None
        self.model = resolve_model(self.spec.id, model)
        self.timeout_ms = timeout_ms
        self._client = None
        self._check_sdk()

    # -- setup -------------------------------------------------------------
    @property
    def api_key(self) -> str:
        key = resolve_key(self.spec.id, self._api_key_override)
        if not key:
            raise missing_key_error(self.spec)
        return key

    def _check_sdk(self) -> None:
        if self.provider == "gemini" and genai is None:
            raise RuntimeError("google-genai is not installed. Run: pip install google-genai")
        if self.provider == "openai" and OpenAI is None:
            raise RuntimeError("openai is not installed. Run: pip install openai")
        if self.provider == "anthropic" and anthropic is None:
            raise RuntimeError("anthropic is not installed. Run: pip install anthropic")

    def _get_client(self):
        if self._client is None:
            key = self.api_key
            if self.provider == "gemini":
                if self.timeout_ms:
                    self._client = genai.Client(
                        api_key=key, http_options=types.HttpOptions(timeout=self.timeout_ms)
                    )
                else:
                    self._client = genai.Client(api_key=key)
            elif self.provider == "openai":
                kwargs = {"api_key": key}
                if self.timeout_ms:
                    kwargs["timeout"] = self.timeout_ms / 1000.0
                self._client = OpenAI(**kwargs)
            else:
                kwargs = {"api_key": key}
                if self.timeout_ms:
                    kwargs["timeout"] = self.timeout_ms / 1000.0
                self._client = anthropic.Anthropic(**kwargs)
        return self._client

    # -- public API --------------------------------------------------------
    def generate_json(self, parts: Sequence[TextOrImage], schema, system: Optional[str] = None,
                      temperature: float = 0.0, model: Optional[str] = None,
                      max_tokens: Optional[int] = None) -> str:
        """One structured generation; returns the raw JSON text for the caller."""
        model = model or self.model
        if self.provider == "gemini":
            return self._gemini_generate(parts, schema, system, temperature, model)
        if self.provider == "openai":
            return self._openai_generate(parts, schema, system, temperature, model, max_tokens)
        return self._anthropic_generate(parts, schema, system, temperature, model, max_tokens)

    def search_json(self, instruction: str, schema, temperature: float = 0.1,
                    model: Optional[str] = None) -> str:
        """One live web-search-grounded call; returns the raw JSON text."""
        model = model or self.model
        if self.provider == "gemini":
            return self._gemini_search(instruction, schema, temperature, model)
        if self.provider == "openai":
            return self._openai_search(instruction, schema, model)
        return self._anthropic_search(instruction, schema, model)

    # -- Gemini ------------------------------------------------------------
    def _gemini_generate(self, parts, schema, system, temperature, model) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature,
        )
        contents = [
            p if isinstance(p, str) else types.Part.from_bytes(data=p.data, mime_type=p.mime)
            for p in parts
        ]
        resp = self._get_client().models.generate_content(
            model=model, contents=contents, config=config
        )
        return resp.text or ""

    def _gemini_search(self, instruction, schema, temperature, model) -> str:
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature,
        )
        resp = self._get_client().models.generate_content(
            model=model, contents=instruction, config=config
        )
        return resp.text or ""

    # -- OpenAI ------------------------------------------------------------
    @staticmethod
    def _openai_parts(parts) -> List[Dict]:
        out: List[Dict] = []
        for p in parts:
            if isinstance(p, str):
                out.append({"type": "text", "text": p})
            else:
                out.append({"type": "image_url", "image_url": {"url": _data_uri(p)}})
        return out

    @staticmethod
    def _openai_text(resp) -> str:
        return resp.choices[0].message.content or ""

    def _openai_generate(self, parts, schema, system, temperature, model, max_tokens) -> str:
        client = self._get_client()
        messages: List[Dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": self._openai_parts(parts)})
        kwargs: Dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "result",
                    "schema": schema.model_json_schema(),
                    "strict": False,
                },
            },
        }
        if max_tokens:
            kwargs["max_completion_tokens"] = max_tokens
        try:
            return self._openai_text(client.chat.completions.create(**kwargs))
        except Exception as e:
            msg = str(e)
            # Some models reject json_schema/temperature/max token params —
            # retry once without the offending parameter before giving up.
            droppable = [
                ("response_format", "response_format"),
                ("temperature", "temperature"),
                ("max_completion_tokens", "max_completion_tokens"),
                ("json_schema", "response_format"),
            ]
            for marker, param in droppable:
                if marker in msg.lower() and param in kwargs:
                    kwargs.pop(param)
                    break
            else:
                raise
        return self._openai_text(client.chat.completions.create(**kwargs))

    def _openai_search(self, instruction, schema, model) -> str:
        try:
            resp = self._get_client().responses.create(
                model=model, input=instruction, tools=[{"type": "web_search"}]
            )
        except Exception as e:
            if is_unsupported_search(str(e)):
                raise UnsupportedSearchError(str(e)) from e
            raise
        return getattr(resp, "output_text", "") or ""

    # -- Anthropic ---------------------------------------------------------
    @staticmethod
    def _anthropic_parts(parts) -> List[Dict]:
        out: List[Dict] = []
        for p in parts:
            if isinstance(p, str):
                out.append({"type": "text", "text": p})
            else:
                out.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": p.mime,
                        "data": base64.b64encode(p.data).decode("ascii"),
                    },
                })
        return out

    def _anthropic_generate(self, parts, schema, system, temperature, model, max_tokens) -> str:
        client = self._get_client()
        kwargs: Dict = {
            "model": model,
            "max_tokens": max_tokens or 32000,
            "messages": [{"role": "user", "content": self._anthropic_parts(parts)}],
            "tools": [{
                "name": "emit_result",
                "description": "Return the structured result.",
                "input_schema": schema.model_json_schema(),
            }],
            "tool_choice": {"type": "tool", "name": "emit_result"},
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        try:
            resp = client.messages.create(**kwargs)
        except Exception as e:
            msg = str(e)
            if "temperature" in msg.lower() and "temperature" in kwargs:
                kwargs.pop("temperature")
                resp = client.messages.create(**kwargs)
            else:
                raise
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                return json.dumps(block.input)
        raise RuntimeError("Anthropic returned no structured tool-use block.")

    def _anthropic_search(self, instruction, schema, model) -> str:
        try:
            resp = self._get_client().messages.create(
                model=model,
                max_tokens=8000,
                messages=[{"role": "user", "content": instruction}],
                tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
            )
        except Exception as e:
            if is_unsupported_search(str(e)):
                raise UnsupportedSearchError(str(e)) from e
            raise
        return "".join(
            getattr(b, "text", "") for b in resp.content
            if getattr(b, "type", None) == "text"
        )
