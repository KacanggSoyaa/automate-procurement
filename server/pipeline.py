"""End-to-end ITB -> specification sheet pipeline shared by the API and CLI."""
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extractors.pdf_extractor import PDFExtractor  # noqa: E402
from extractors.office_extractor import OfficeExtractor  # noqa: E402
from processors.ai_processor import AIProcessor  # noqa: E402
from generators.enhanced_spec_sheet import EnhancedSpecSheetGenerator  # noqa: E402
from generators.rfq_email_generator import RFQEmailGenerator  # noqa: E402

ProgressCb = Optional[Callable[[str, int, int, str], None]]


def _normalise_skip(skip_files: Optional[List[str]]) -> set:
    """Normalise user-listed filenames for case-insensitive exact matching."""
    if not skip_files:
        return set()
    return {str(name).strip().lower() for name in skip_files if str(name).strip()}


def run_pipeline(
    input_dir: str,
    output_path: str,
    model: Optional[str] = None,
    include_images: bool = True,
    pattern: str = "*",
    skip_files: Optional[List[str]] = None,
    progress: ProgressCb = None,
) -> Dict:
    """Run the full ITB -> spec sheet pipeline for a folder of uploaded files.

    Every matching PDF, Word (.docx) and Excel (.xlsx/.xlsm) file is read by
    default. ``skip_files`` lets the caller exclude specific documents by exact
    filename (case-insensitive); skipped files are still listed in the source
    footer as evidence but are never sent to Gemini for classification.
    """

    def emit(stage: str, current: int, total: int, message: str):
        """Forward a progress update to the caller's callback, if any."""
        if progress:
            progress(stage, current, total, message)

    pdf_ext = PDFExtractor()
    office_ext = OfficeExtractor()

    emit("extract", 0, 1, "Scanning uploaded PDF / Word / Excel files...")
    results = pdf_ext.extract_itb_folder(input_dir, pattern=pattern)
    results += office_ext.extract_office_folder(input_dir, pattern=pattern)
    if not results:
        raise RuntimeError(
            f"No readable PDF, Word or Excel files matched '{pattern}' in the upload."
        )
    errors = [r for r in results if r.get("error")]
    for r in errors:
        emit("extract", 0, 1, f"Skipped {r['filename']}: {r['error']}")
    ok = [r for r in results if not r.get("error")]
    emit("extract", 1, 1, f"Read {len(ok)} file(s)")

    # Every PDF is read by default. Only filenames the user explicitly listed
    # in the settings are excluded (exact match, case-insensitive), so the real
    # item document is never skipped by mistake.
    skipped = _normalise_skip(skip_files)
    docs = [r for r in ok if r["filename"].strip().lower() not in skipped]
    for r in ok:
        if r["filename"].strip().lower() in skipped:
            emit("extract", 1, 1, f"Skipped by settings: {r['filename']}")
    content = "\n\n".join(r.get("content", "") for r in docs)

    # Every uploaded document is kept as evidence for the source footer.
    source_files = [r["filename"] for r in ok]

    image_paths = []
    if include_images:
        emit("images", 0, 1, "Collecting images / screenshots...")
        screenshots = pdf_ext.collect_image_files(input_dir)
        image_paths += screenshots
        source_files += [Path(p).name for p in screenshots]
        render_dir = str(Path(output_path).parent / "extracted_images")
        for r in docs:
            if r["path"].lower().endswith(".pdf"):
                image_paths += pdf_ext.render_image_pages(r["path"], render_dir)
        emit("images", 1, 1, f"Found {len(image_paths)} image(s)")

    processor = AIProcessor(model=model)

    def ai_progress(kind: str, i: int, n: int):
        emit("classify", i, n, f"Classifying {kind} {i}/{n} with Gemini")

    reqs = processor.classify(content, image_paths=image_paths, progress=ai_progress)

    line_items = reqs["line_items"]
    extracted_data = {
        "files_processed": len(ok),
        "summary": f"Analyzed {len(ok)} ITB document(s)",
        "source_files": source_files,
        "meta": reqs.get("meta", {}),
        "line_items": line_items,
        "line_items_count": len(line_items),
        "technical_requirements": reqs["technical"],
        "submission_rules": reqs["submission"],
        "mandatory_requirements": reqs["mandatory"],
        "commercial_requirements": reqs["commercial"],
        "dates": reqs["dates"],
    }

    # One copy-ready RFQ email per line item (deterministic, no API calls).
    extracted_data["rfq_emails"] = RFQEmailGenerator().build_emails(extracted_data)

    emit("generate", 0, 1, "Generating specification sheet...")
    generator = EnhancedSpecSheetGenerator()
    out = generator.generate(extracted_data, output_path)
    emit("generate", 1, 1, "Specification sheet ready")

    return {"output_path": out, "data": extracted_data}
