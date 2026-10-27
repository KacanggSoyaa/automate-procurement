"""Validation and staging for user-supplied job uploads.

Files are streamed into a temporary staging directory, checked for size,
extension, magic bytes and (for Office/zip files) unsafe compression ratios,
and only then moved into the job's upload directory. Rejecting a batch leaves
the job's existing files untouched.
"""
import os
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

ALLOWED_EXTENSIONS = frozenset({
    ".pdf", ".docx", ".xlsx", ".xlsm",
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff",
})
_ZIP_EXTENSIONS = frozenset({".docx", ".xlsx", ".xlsm"})

_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

_MAX_NAME_LENGTH = 180


class UploadValidationError(ValueError):
    """Raised when an upload is missing, unsafe, too large or malformed."""


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default))))
    except ValueError:
        return default


MAX_FILE_BYTES = _env_int("MAX_UPLOAD_FILE_MB", 100) * 1024 * 1024
MAX_TOTAL_BYTES = _env_int("MAX_UPLOAD_TOTAL_MB", 250) * 1024 * 1024
MAX_FILES = _env_int("MAX_UPLOAD_FILES", 100)
MAX_ZIP_UNCOMPRESSED_BYTES = _env_int("MAX_UPLOAD_ZIP_MB", 500) * 1024 * 1024
MAX_ZIP_RATIO = _env_int("MAX_UPLOAD_ZIP_RATIO", 200)
# Give multipart framing a little headroom while still rejecting huge bodies
# before they are parsed or buffered by the upload handler.
MAX_REQUEST_BYTES = MAX_TOTAL_BYTES + 10 * 1024 * 1024


def _safe_name(raw: Optional[str]) -> str:
    """Return a safe base filename or raise a validation error."""
    name = (raw or "").replace("\\", "/").split("/")[-1].strip()
    name = "".join(ch for ch in name if ord(ch) >= 32 and ch != "\x7f").strip(" .")
    if not name or name in (".", ".."):
        raise UploadValidationError("A file is missing a valid filename.")

    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise UploadValidationError(
            f"Unsupported file type '{ext or name}'. Allowed types: {allowed}."
        )

    stem = Path(name).stem
    if stem.split(".")[0].strip(" .").upper() in _RESERVED_NAMES:
        raise UploadValidationError(f"'{name}' is not an allowed filename.")

    if len(name) > _MAX_NAME_LENGTH:
        keep = max(1, _MAX_NAME_LENGTH - len(ext))
        name = name[:keep].rstrip(" .") + ext
    return name


def _signature_ok(path: Path, ext: str) -> bool:
    with path.open("rb") as handle:
        head = handle.read(1024)
    if not head:
        return False
    if ext == ".pdf":
        return b"%PDF-" in head
    if ext == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in (".jpg", ".jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == ".gif":
        return head.startswith((b"GIF87a", b"GIF89a"))
    if ext == ".bmp":
        return head.startswith(b"BM")
    if ext == ".webp":
        return head.startswith(b"RIFF") and head[8:12] == b"WEBP"
    if ext in (".tif", ".tiff"):
        return head.startswith((b"II*\x00", b"MM\x00*"))
    if ext in _ZIP_EXTENSIONS:
        return head.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
    return False


def _check_zip(path: Path, name: str) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
    except (zipfile.BadZipFile, OSError) as exc:
        raise UploadValidationError(f"'{name}' is not a valid Office file.") from exc
    if not entries:
        raise UploadValidationError(f"'{name}' is empty.")
    uncompressed = sum(entry.file_size for entry in entries)
    compressed = sum(max(entry.compress_size, 1) for entry in entries)
    if uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
        raise UploadValidationError(f"'{name}' expands to an unsupported size.")
    if uncompressed > 20 * 1024 * 1024 and uncompressed / compressed > MAX_ZIP_RATIO:
        raise UploadValidationError(f"'{name}' has an unsafe compression ratio.")


def _validate_content(path: Path, name: str) -> None:
    ext = Path(name).suffix.lower()
    if not _signature_ok(path, ext):
        raise UploadValidationError(f"'{name}' does not match its file type.")
    if ext in _ZIP_EXTENSIONS:
        _check_zip(path, name)


def save_uploads(files: Sequence, destination: Path,
                 existing_names: Optional[Iterable[str]] = None,
                 allow_replace: bool = False) -> List[str]:
    """Validate and store ``files`` under ``destination``.

    ``allow_replace`` is used when adding files to an existing job: re-uploading
    the same name is how a document's changed content is picked up. Duplicate
    names within one batch are always rejected.
    """
    destination = Path(destination)
    files = list(files)
    existing = {Path(name).name.casefold() for name in (existing_names or [])}
    if len(files) > MAX_FILES:
        raise UploadValidationError(f"At most {MAX_FILES} files are allowed per job.")

    staging = destination / f".upload-{uuid.uuid4().hex}"
    try:
        destination.mkdir(parents=True, exist_ok=True)
        staging.mkdir()
        staged = []
        seen = set()
        total = 0

        for upload in files:
            name = _safe_name(getattr(upload, "filename", None))
            key = name.casefold()
            if key in seen:
                raise UploadValidationError(f"Duplicate upload filename: '{name}'.")
            seen.add(key)
            if not allow_replace and (key in existing or (destination / name).exists()):
                raise UploadValidationError(f"A file named '{name}' already exists.")

            temp = staging / f"{len(staged):04d}-{uuid.uuid4().hex}"
            size = 0
            with temp.open("wb") as out:
                source = getattr(upload, "file", None)
                if source is None:
                    raise UploadValidationError(f"'{name}' could not be read.")
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    total += len(chunk)
                    if size > MAX_FILE_BYTES:
                        raise UploadValidationError(f"'{name}' is too large.")
                    if total > MAX_TOTAL_BYTES:
                        raise UploadValidationError("The upload is too large.")
                    out.write(chunk)
            if size == 0:
                raise UploadValidationError(f"'{name}' is empty.")
            _validate_content(temp, name)
            staged.append((temp, name))

        if len(existing | seen) > MAX_FILES:
            raise UploadValidationError(f"At most {MAX_FILES} files are allowed per job.")

        for temp, name in staged:
            os.replace(temp, destination / name)
        return [name for _, name in staged]
    except UploadValidationError:
        raise
    except Exception as exc:
        raise UploadValidationError(f"Could not save the upload: {exc}") from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)
