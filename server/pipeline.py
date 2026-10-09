"""End-to-end ITB -> specification sheet pipeline shared by the API and CLI."""
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extractors.pdf_extractor import PDFExtractor  # noqa: E402
from processors.ai_processor import AIProcessor  # noqa: E402
from generators.enhanced_spec_sheet import EnhancedSpecSheetGenerator  # noqa: E402

ProgressCb = Optional[Callable[[str, int, int, str], None]]

# Filename hints for documents that only contain rules, terms or how-to text.
# These are never allowed to contribute line items or project metadata.
BOILERPLATE_HINTS = (
    "hse", "safety", "rules", "regulation", "terms", "conditions", "gtc",
    "guide", "manual", "policy", "procedure", "instruction",
)

# Filename hints for the actual bid/spec document that holds the real items.
PRIMARY_HINTS = (
    "itb", "rfq", "tender", "bid", "quotation", "quote", "spec", "price",
    "boq", "schedule of rates", "requisition",
)


def is_boilerplate(filename: str) -> bool:
    """Return True when a document is terms/conditions, safety or a user guide.

    A filename that also carries a primary hint (e.g. "ITB Terms") is treated
    as a real bid document so the actual ITB is never skipped by mistake.
    """
    name = filename.lower()
    if any(hint in name for hint in PRIMARY_HINTS):
        return False
    return any(hint in name for hint in BOILERPLATE_HINTS)


def select_bid_documents(results: List[Dict]) -> List[Dict]:
    """Choose which documents should be sent for line-item extraction.

    Boilerplate documents (HSE, GTC, user guides) are skipped. If every
    document looks like boilerplate we fall back to the full set so the model
    is never handed nothing to read.
    """
    primary = [r for r in results if not is_boilerplate(r["filename"])]
    return primary or results


def run_pipeline(
    input_dir: str,
    output_path: str,
    model: Optional[str] = None,
    include_images: bool = True,
    pattern: str = "*",
    progress: ProgressCb = None,
) -> Dict:
    """Run the full ITB -> spec sheet pipeline for a folder of uploaded files."""

    def emit(stage: str, current: int, total: int, message: str):
        """Forward a progress update to the caller's callback, if any."""
        if progress:
            progress(stage, current, total, message)

    pdf_ext = PDFExtractor()

    emit("extract", 0, 1, "Scanning uploaded PDF files...")
    results = pdf_ext.extract_itb_folder(input_dir, pattern=pattern)
    if not results:
        raise RuntimeError(f"No PDF files matched '{pattern}' in the upload.")
    errors = [r for r in results if r.get("error")]
    for r in errors:
        emit("extract", 0, 1, f"Skipped {r['filename']}: {r['error']}")
    ok = [r for r in results if not r.get("error")]
    emit("extract", 1, 1, f"Read {len(ok)} PDF file(s)")

    # Only the actual bid/spec documents are sent to Gemini for line items.
    # Terms, HSE rules and user guides are listed as evidence but never
    # classified, which keeps the item list clean and the run fast.
    docs = select_bid_documents(ok)
    for r in ok:
        if r not in docs:
            emit("extract", 1, 1, f"Skipped non-item document: {r['filename']}")
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

    emit("generate", 0, 1, "Generating specification sheet...")
    generator = EnhancedSpecSheetGenerator()
    out = generator.generate(extracted_data, output_path)
    emit("generate", 1, 1, "Specification sheet ready")

    return {"output_path": out, "data": extracted_data}
