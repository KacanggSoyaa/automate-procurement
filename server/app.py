"""FastAPI backend for the Automate Procurement web UI."""
import os
from pathlib import Path
from typing import List, Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .ai_providers import PROVIDERS, get_spec, provider_label
from .auth import (
    COOKIE_NAME,
    SESSION_DAYS,
    bootstrap_admin,
    current_user,
    decode_token,
    make_token,
    require_admin,
    user_store,
)
from .jobs import job_manager
from .supplier_store import supplier_store
from .suppliers import quota_status, supplier_finder


class RenameRequest(BaseModel):
    """Body for renaming a saved history entry."""
    title: str


class LoginRequest(BaseModel):
    """Credentials submitted from the login screen."""
    username: str
    password: str


class CreateUserRequest(BaseModel):
    """Body for an admin creating a new user."""
    username: str
    password: str
    display_name: Optional[str] = ""
    role: Optional[str] = "user"


class SetPasswordRequest(BaseModel):
    """Body for an admin resetting a user's password."""
    password: str


class AiSettingsRequest(BaseModel):
    """Body for updating the caller's AI provider / key / model.

    Send ``provider`` to switch the active provider, ``api_key`` to set (or
    replace) that provider's key, ``clear_key=true`` to remove it, ``model``
    to change that provider's model, and ``supplier_search_provider`` to
    choose whether supplier search also uses the active provider. Omitted
    fields are left unchanged.
    """
    provider: Optional[str] = None
    supplier_search_provider: Optional[bool] = None
    api_key: Optional[str] = None
    clear_key: bool = False
    model: Optional[str] = None


class SupplierPayload(BaseModel):
    """User-editable fields of a curated supplier directory entry."""
    company_name: Optional[str] = ""
    website: Optional[str] = ""
    email: Optional[str] = ""
    contact: Optional[str] = ""
    source: Optional[str] = ""
    notes: Optional[str] = ""
    tags: Optional[str] = ""


class SupplierImportRequest(BaseModel):
    """Bulk-add a list of suppliers (e.g. one run's shortlist) to the directory."""
    suppliers: List[SupplierPayload] = []

app = FastAPI(title="Automate Procurement API", version="0.1.0")

# The Vite dev server runs on a different port, so allow cross-origin calls.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths that must stay reachable without a session.
_PUBLIC_PATHS = {
    "/api/health",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
    "/api/auth/status",
}


@app.middleware("http")
async def require_auth(request: Request, call_next):
    """Gate every /api route behind a valid session cookie.

    Auth endpoints and the health probe stay public so the SPA can render the
    login screen and discover whether any users exist yet.
    """
    path = request.url.path
    if path.startswith("/api") and path not in _PUBLIC_PATHS:
        token = request.cookies.get(COOKIE_NAME)
        payload = decode_token(token) if token else None
        if not payload or not user_store.get(payload.get("sub", "")):
            return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    return await call_next(request)


# Create the first admin from ADMIN_USERNAME / ADMIN_PASSWORD on startup.
bootstrap_admin()


@app.get("/api/health")
def health():
    """Liveness probe used to check the backend is up."""
    return {"status": "ok"}


# ------------------------------------------------------------------- auth
@app.post("/api/auth/login")
def login(body: LoginRequest, response: Response):
    """Verify credentials and set the session cookie."""
    user = user_store.authenticate(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    response.set_cookie(
        key=COOKIE_NAME,
        value=make_token(user),
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=False,  # set True behind HTTPS in production
        path="/",
    )
    return {"user": user}


@app.post("/api/auth/logout")
def logout(response: Response):
    """Clear the session cookie."""
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request):
    """Return the current user, or 401 when not signed in."""
    token = request.cookies.get(COOKIE_NAME)
    payload = decode_token(token) if token else None
    user = user_store.get(payload.get("sub", "")) if payload else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"user": user}


@app.get("/api/auth/status")
def auth_status():
    """Tell the login screen whether any account exists yet."""
    return {"has_users": user_store.count() > 0}


# ------------------------------------------------------- user admin (admin)
@app.get("/api/users")
def list_users(_: dict = Depends(require_admin)):
    """List all users (admin only)."""
    return {"users": user_store.list()}


@app.post("/api/users")
def create_user(body: CreateUserRequest, _: dict = Depends(require_admin)):
    """Create a new user (admin only)."""
    try:
        user = user_store.create(
            body.username, body.password, body.display_name or "", body.role or "user"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return user


@app.post("/api/users/{user_id}/password")
def set_user_password(
    user_id: str, body: SetPasswordRequest, _: dict = Depends(require_admin)
):
    """Reset a user's password (admin only)."""
    try:
        user = user_store.set_password(user_id, body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


@app.delete("/api/users/{user_id}")
def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    """Delete a user (admin only). Cannot delete your own account."""
    if admin.get("id") == user_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")
    if not user_store.delete(user_id):
        raise HTTPException(status_code=404, detail="User not found.")
    return {"ok": True, "id": user_id}



@app.get("/api/quota")
def get_quota():
    """Last-known Google-Search grounding quota state shown in the header."""
    return quota_status()


def _ai_settings_payload(user_id: str) -> dict:
    """Full AI-settings payload: active provider, per-provider keys/models."""
    u = user_store.get(user_id) or {}
    keys = u.get("keys") or {}
    active = get_spec(u.get("ai_provider")).id
    providers = []
    for pid, spec in PROVIDERS.items():
        info = keys.get(pid) or {}
        providers.append(
            {
                "id": pid,
                "label": spec.label,
                "default_model": spec.default_model,
                "models": list(spec.models),
                "key_url": spec.key_url,
                "env_key": spec.env_key,
                "env_key_available": bool(os.environ.get(spec.env_key)),
                "has_api_key": bool(info.get("has_api_key")),
                "api_key_hint": info.get("api_key_hint"),
                "model": u.get(f"{pid}_model"),
            }
        )
    gemini = next(p for p in providers if p["id"] == "gemini")
    return {
        "provider": active,
        "supplier_search_provider": u.get("supplier_search_provider", True),
        "providers": providers,
        # Legacy Gemini-only fields kept for older clients.
        "has_api_key": gemini["has_api_key"],
        "api_key_hint": gemini["api_key_hint"],
        "model": gemini["model"],
        "env_key_available": gemini["env_key_available"],
        "default_model": gemini["default_model"],
        "fallback_models": list(get_spec("gemini").fallback_models),
    }


@app.get("/api/settings/ai")
def get_ai_settings(user: dict = Depends(current_user)):
    """Return the caller's AI settings (masked keys, never raw secrets)."""
    return _ai_settings_payload(user.get("id", ""))


@app.put("/api/settings/ai")
def update_ai_settings(body: AiSettingsRequest, user: dict = Depends(current_user)):
    """Save or clear the caller's AI provider, keys and/or model choices."""
    if body.provider is not None:
        try:
            get_spec(body.provider)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    if body.api_key is not None and body.api_key.strip() and len(body.api_key.strip()) < 10:
        raise HTTPException(status_code=400, detail="That API key looks too short.")
    try:
        entry = user_store.set_ai_settings(
            user.get("id", ""),
            provider=body.provider,
            supplier_search_provider=body.supplier_search_provider,
            api_key=body.api_key,
            clear_key=body.clear_key,
            model=body.model,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if entry is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return _ai_settings_payload(user.get("id", ""))


def _parse_skip_files(raw: Optional[str]) -> List[str]:
    """Split the settings textarea into a clean list of filenames to skip."""
    if not raw:
        return []
    parts = raw.replace(",", "\n").splitlines()
    return [p.strip() for p in parts if p.strip()]


def _owner_scope(user: dict) -> Optional[str]:
    """The owner id a request should be limited to.

    Admins see everything (``None`` = no filter); regular users are scoped to
    their own account id.
    """
    return None if user.get("role") == "admin" else user.get("id")


def _user_api_key(user: dict, provider: str = "gemini") -> Optional[str]:
    """The key to use for a request: the user's own for this provider, else env."""
    return user_store.api_key(user.get("id", ""), provider) or None


def _user_settings(user: dict) -> dict:
    """The caller's stored AI settings record (empty dict when unknown)."""
    return user_store.get(user.get("id", "")) or {}


def _require_personal_key(user: dict, provider: str) -> None:
    """Reject AI actions until the caller has saved their own key for ``provider``."""
    if not user_store.api_key(user.get("id", ""), provider):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Add your {provider_label(provider)} API key in Settings "
                "before using the system."
            ),
        )


def _owned_job(job_id: str, user: dict):
    """Load a job, raising 404 unless it belongs to the requesting user."""
    job = job_manager.get(job_id)
    if not job or not job_manager.owned_by(job_id, _owner_scope(user)):
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@app.post("/api/jobs")
async def create_job(
    files: List[UploadFile] = File(...),
    model: Optional[str] = Form(None),
    include_images: bool = Form(True),
    pattern: str = Form("*"),
    skip_files: Optional[str] = Form(None),
    user: dict = Depends(current_user),
):
    """Accept an uploaded ITB folder and queue a processing job.

    ``skip_files`` is a newline- or comma-separated list of exact filenames the
    user chose to exclude from item extraction. The job is owned by the caller.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    entry = _user_settings(user)
    provider = get_spec(entry.get("ai_provider")).id
    _require_personal_key(user, provider)
    job = job_manager.create(
        files,
        model=model or entry.get(f"{provider}_model"),
        include_images=include_images,
        pattern=pattern,
        skip_files=_parse_skip_files(skip_files),
        owner=user.get("id"),
        api_key=_user_api_key(user, provider),
        provider=provider,
    )
    return job.to_dict()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, user: dict = Depends(current_user)):
    """Return the current status, logs and results of a job you own."""
    return _owned_job(job_id, user).to_dict()


@app.get("/api/history")
def list_history(user: dict = Depends(current_user)):
    """Return the saved history of finished ITB runs the caller owns, newest first."""
    return {"jobs": job_manager.history(_owner_scope(user))}


@app.delete("/api/history/{job_id}")
def delete_history(job_id: str, user: dict = Depends(current_user)):
    """Remove a run (that you own) from history and delete its workspace."""
    if not job_manager.delete(job_id, _owner_scope(user)):
        raise HTTPException(status_code=404, detail="History entry not found.")
    return {"ok": True, "id": job_id}


@app.patch("/api/history/{job_id}")
def rename_history(job_id: str, body: RenameRequest, user: dict = Depends(current_user)):
    """Rename a saved history entry you own (sets a custom display title)."""
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title must not be empty.")
    entry = job_manager.rename(job_id, title, _owner_scope(user))
    if entry is None:
        raise HTTPException(status_code=404, detail="History entry not found.")
    return entry


@app.post("/api/jobs/{job_id}/files")
async def add_job_files(
    job_id: str, files: List[UploadFile] = File(...), user: dict = Depends(current_user)
):
    """Append files to a finished job you own and reprocess only the new ones."""
    job = _owned_job(job_id, user)
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    # Keep the provider/model the run originally used so merged results match.
    provider = ((job.config or {}).get("provider") or "gemini").lower()
    _require_personal_key(user, provider)
    job = job_manager.add_and_reprocess(
        job_id, files, api_key=_user_api_key(user, provider), provider=provider
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.to_dict()


@app.get("/api/jobs/{job_id}/versions/{n}/download")
def download_version(job_id: str, n: int, user: dict = Depends(current_user)):
    """Download a historical version snapshot (zip) of a finished job you own."""
    _owned_job(job_id, user)
    zip_path = job_manager.version_zip(job_id, n)
    if zip_path is None:
        raise HTTPException(status_code=404, detail="Version not found.")
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"specification_sheet_{zip_path.stem}_{job_id}.zip",
    )


@app.post("/api/jobs/{job_id}/suppliers")
def find_suppliers(job_id: str, mode: str = "all", user: dict = Depends(current_user)):
    """Start supplier search for a finished run you own.

    ``mode=all`` (default) runs one batched search covering every product at
    once; ``mode=per_item`` runs a separate search per line item.
    """
    _owned_job(job_id, user)
    entry = _user_settings(user)
    # The toggle decides whether supplier search follows the user's chosen
    # provider or stays pinned to Gemini (the classic grounding behaviour).
    if entry.get("supplier_search_provider", True):
        provider = get_spec(entry.get("ai_provider")).id
    else:
        provider = "gemini"
    _require_personal_key(user, provider)
    err = supplier_finder.start(
        job_id,
        mode,
        api_key=_user_api_key(user, provider),
        provider=provider,
        model=entry.get(f"{provider}_model"),
    )
    if err:
        if err == "Job not found.":
            status = 404
        elif err == "Supplier search is already running.":
            status = 409
        else:
            status = 400
        raise HTTPException(status_code=status, detail=err)
    return job_manager.get(job_id).to_dict()


@app.get("/api/jobs/{job_id}/suppliers/download.csv")
def suppliers_csv(job_id: str, user: dict = Depends(current_user)):
    """Export every shortlisted supplier as a CSV for the buyer's records."""
    _owned_job(job_id, user)
    content = supplier_finder.build_csv(job_id)
    if content is None:
        raise HTTPException(status_code=404, detail="No supplier data found.")
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="suppliers_{job_id}.csv"'},
    )


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str, user: dict = Depends(current_user)):
    """Stream the generated specification sheet DOCX for a finished job you own."""
    job = _owned_job(job_id, user)
    if job.status != "done" or not job.output_path or not Path(job.output_path).exists():
        raise HTTPException(status_code=409, detail="Result not ready.")
    return FileResponse(
        job.output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="specification_sheet.docx",
    )


# --------------------------------------------------------------- supplier list
@app.get("/api/suppliers")
def list_suppliers(scope: str = "mine", user: dict = Depends(current_user)):
    """Return curated suppliers. ``scope=mine`` (default) is your own list (plus
    shared entries); ``scope=all`` shows every user's suppliers, marked with an
    ``owner`` so the UI can lock the ones you do not own.
    """
    scope = "all" if scope == "all" else "mine"
    return {"suppliers": supplier_store.list(owner=user.get("id"), scope=scope)}


@app.post("/api/suppliers")
def create_supplier(body: SupplierPayload, user: dict = Depends(current_user)):
    """Add one supplier to your master list."""
    entry = supplier_store.add(body.model_dump(), owner=user.get("id"))
    if entry is None:
        raise HTTPException(status_code=400, detail="A supplier needs a name or website.")
    return entry


@app.post("/api/suppliers/import")
def import_suppliers(body: SupplierImportRequest, user: dict = Depends(current_user)):
    """Bulk-add suppliers (skips duplicates) and report the counts."""
    return supplier_store.add_many([s.model_dump() for s in body.suppliers], owner=user.get("id"))


@app.patch("/api/suppliers/{supplier_id}")
def update_supplier(supplier_id: str, body: SupplierPayload, user: dict = Depends(current_user)):
    """Update one curated supplier's fields (only if you own it)."""
    entry = supplier_store.update(supplier_id, body.model_dump(exclude_unset=True), owner=user.get("id"))
    if entry is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    return entry


@app.delete("/api/suppliers/{supplier_id}")
def delete_supplier(supplier_id: str, user: dict = Depends(current_user)):
    """Remove one supplier from the master list (only if you own it)."""
    if not supplier_store.delete(supplier_id, owner=user.get("id")):
        raise HTTPException(status_code=404, detail="Supplier not found.")
    return {"ok": True, "id": supplier_id}
