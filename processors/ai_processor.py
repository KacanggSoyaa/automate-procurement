import os
import json
import time
import hashlib
import random
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


class SpecPair(BaseModel):
    parameter: str
    value: str


class LineItem(BaseModel):
    item_no: Optional[str] = None
    item_name: Optional[str] = None
    item_number: Optional[str] = None
    description: Optional[str] = None
    qty: Optional[str] = None
    uom: Optional[str] = None
    specs: List[SpecPair] = []


class Classification(BaseModel):
    project_ref: Optional[str] = None
    project_title: Optional[str] = None
    delivery_location: Optional[str] = None
    buyer: Optional[str] = None
    line_items: List[LineItem] = []
    technical_requirements: List[str] = []
    commercial_requirements: List[str] = []
    submission_rules: List[str] = []
    mandatory_requirements: List[str] = []
    dates: List[str] = []


SYSTEM_INSTRUCTION = (
    "You are a procurement analyst reading an Invitation To Bid (ITB) / Request For Quotation (RFQ) document. "
    "Your job is to separate REAL purchasable line items from general requirements, rules, terms and conditions.\n\n"
    "LINE ITEMS are actual goods or services the buyer wants to procure (physical products, materials or services), "
    "usually with a quantity, unit (pcs, set, lot, kg, m, PC, etc.) or a part/material number. For each line item fill:\n"
    "  - item_no: the line/sequence number if shown\n"
    "  - item_name: a short descriptive name (often ALL CAPS, e.g. 'DISC DRIVE, MAG, WD10EZEX, HRD DISC, SATA')\n"
    "  - item_number: the buyer's item/material/part number if shown\n"
    "  - description: the full item description\n"
    "  - qty: quantity as text; uom: unit of measure as text\n"
    "  - specs: a list of {parameter, value} pairs for the item's technical specification key details, when available\n\n"
    "REQUIREMENTS are clauses, instructions, rules, conditions, evaluation criteria, terms and conditions, submission "
    "instructions, deadlines, HSE rules, legal text, boilerplate, etc. These are NOT line items and must NEVER be placed "
    "in line_items.\n\n"
    "Classify each meaningful statement only into line_items (genuine purchasable items) or one of the requirement "
    "categories: technical_requirements, commercial_requirements, submission_rules, mandatory_requirements, dates.\n"
    "Also extract project_ref (reference number), project_title, delivery_location and buyer if present. "
    "Keep original wording. Do not invent data. Omit irrelevant boilerplate to stay concise. "
    "To avoid overwhelming output, return the most relevant requirements only (at most about 40 per category per section)."
)

IMAGE_INSTRUCTION = (
    "The following image(s) are screenshots or pictures taken from the ITB / RFQ / price sheet. "
    "Read the text, tables and specifications shown inside the images. Extract every REAL purchasable line item "
    "with its item name, item number, description, quantity, unit of measure and technical specification details. "
    "Also extract any clearly stated requirements into the matching categories. "
    "Use exactly the same rules as for the document text: do NOT place general clauses, terms or instructions into line_items."
)


class AIProcessor:
    DEFAULT_MODEL = "gemini-3.8-flash"
    FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-flash-latest", "gemini-3.1-flash-lite"]
    MAX_CHARS_PER_CHUNK = 120000
    MAX_IMAGES = 12
    CACHE_VERSION = "v3"
    CACHE_DIR = Path("./data/.ai_cache")

    def __init__(self, model: str = None, api_key: str = None, use_cache: bool = True):
        if genai is None:
            raise RuntimeError(
                "google-genai is not installed. Run: pip install google-genai"
            )
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Get a key from https://aistudio.google.com/apikey "
                "and set it as an environment variable."
            )
        self.client = genai.Client(api_key=self.api_key)
        self.model = model or os.environ.get("GEMINI_MODEL", self.DEFAULT_MODEL)
        self.models = [self.model] + [m for m in self.FALLBACK_MODELS if m != self.model]
        self.use_cache = use_cache
        if self.use_cache:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _chunk(self, text: str) -> List[str]:
        lines = text.split("\n")
        chunks, current = [], []
        size = 0
        for line in lines:
            if size + len(line) > self.MAX_CHARS_PER_CHUNK and current:
                chunks.append("\n".join(current))
                current, size = [], 0
            current.append(line)
            size += len(line) + 1
        if current:
            chunks.append("\n".join(current))
        return chunks

    def _cache_path(self, seed: str, model: str) -> Path:
        key = hashlib.sha256(
            (self.CACHE_VERSION + "\x00" + model + "\x00" + seed).encode("utf-8")
        ).hexdigest()
        return self.CACHE_DIR / f"{key}.json"

    def _generate(self, contents, cache_seed: str, retries: int = 6) -> Classification:
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=Classification,
            temperature=0,
        )
        last_err = None
        for model in self.models:
            cache_path = self._cache_path(cache_seed, model)
            if self.use_cache and cache_path.exists():
                try:
                    return Classification.model_validate_json(
                        cache_path.read_text(encoding="utf-8")
                    )
                except Exception:
                    pass
            for attempt in range(retries):
                try:
                    resp = self.client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=config,
                    )
                    if self.use_cache:
                        cache_path.write_text(resp.text, encoding="utf-8")
                    return Classification.model_validate_json(resp.text)
                except Exception as e:
                    last_err = e
                    msg = str(e)
                    transient = any(c in msg for c in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded"))
                    if not transient:
                        break
                    delay = min(60, 2 ** attempt) + random.uniform(0, 1)
                    time.sleep(delay)
        raise RuntimeError(f"Gemini classification failed on all models: {last_err}")

    def _image_part(self, path: str):
        data = Path(path).read_bytes()
        lower = path.lower()
        if lower.endswith('.png'):
            mime = 'image/png'
        elif lower.endswith(('.jpg', '.jpeg')):
            mime = 'image/jpeg'
        elif lower.endswith('.webp'):
            mime = 'image/webp'
        elif lower.endswith(('.tif', '.tiff')):
            mime = 'image/tiff'
        elif lower.endswith('.bmp'):
            mime = 'image/bmp'
        elif lower.endswith('.gif'):
            mime = 'image/gif'
        else:
            mime = 'image/png'
        return types.Part.from_bytes(data=data, mime_type=mime)

    def _classify_images(self, image_paths: List[str], progress=None) -> Classification:
        image_paths = image_paths[: self.MAX_IMAGES]
        if not image_paths:
            return Classification()
        contents = [IMAGE_INSTRUCTION]
        seed_parts = []
        for p in image_paths:
            try:
                contents.append(self._image_part(p))
                digest = hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]
                seed_parts.append(f"{Path(p).name}:{digest}")
            except Exception:
                continue
        if len(contents) == 1:
            return Classification()
        return self._generate(contents, "IMAGES::" + "|".join(seed_parts))

    @staticmethod
    def _dedupe(values: List[str]) -> List[str]:
        seen, out = set(), []
        for v in values:
            key = " ".join(v.lower().split())
            if key and key not in seen:
                seen.add(key)
                out.append(v)
        return out

    def classify(self, text: str, image_paths: List[str] = None, progress=None) -> Dict:
        chunks = self._chunk(text) if text.strip() else []
        merged = Classification()
        meta = {}

        for i, chunk in enumerate(chunks, 1):
            if progress:
                progress('text', i, len(chunks))
            self._merge(merged, meta, self._generate(chunk, chunk))

        if image_paths:
            if progress:
                progress('images', 1, 1)
            self._merge(merged, meta, self._classify_images(image_paths))

        seen_items, line_items = set(), []
        for item in merged.line_items:
            desc = (item.description or item.item_name or "").strip()
            key = (" ".join(desc.lower().split()), item.item_number, item.qty)
            if desc and key not in seen_items:
                seen_items.add(key)
                line_items.append(item.model_dump())

        return {
            "line_items": line_items,
            "technical": self._dedupe(merged.technical_requirements),
            "commercial": self._dedupe(merged.commercial_requirements),
            "submission": self._dedupe(merged.submission_rules),
            "mandatory": self._dedupe(merged.mandatory_requirements),
            "dates": self._dedupe(merged.dates),
            "meta": meta,
        }

    @staticmethod
    def _merge(merged: Classification, meta: Dict, result: Classification):
        for field in ("project_ref", "project_title", "delivery_location", "buyer"):
            val = getattr(result, field)
            if val and not meta.get(field):
                meta[field] = val
        merged.line_items.extend(result.line_items)
        merged.technical_requirements.extend(result.technical_requirements)
        merged.commercial_requirements.extend(result.commercial_requirements)
        merged.submission_rules.extend(result.submission_rules)
        merged.mandatory_requirements.extend(result.mandatory_requirements)
        merged.dates.extend(result.dates)
