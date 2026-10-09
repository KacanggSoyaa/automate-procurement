"""Deterministic RFQ email builder modelled on generators/rfqEmailFormat.docx.

Produces a single request-for-quotation email covering every extracted line
item, filling the sample's structure from the pipeline's ``meta`` and
``line_items``. No API calls: the wording is a fixed template so results are
reproducible.
"""
import os
from typing import Dict, List, Optional

# Signature appended to the email; override with the RFQ_SIGNATURE env var.
DEFAULT_SIGNATURE = "Best regards,\nProcurement Team"

# Spec parameter names that hold a part / model number.
_PART_KEYS = (
    "manufacturer part number", "part number", "part no", "part no.",
    "model number", "model", "mpn",
)


def _clean(text) -> str:
    """Return a trimmed string, collapsing internal newlines to spaces."""
    return " ".join(str(text or "").split())


def _find_part_number(item: Dict) -> Optional[str]:
    """Pull a part / model number out of an item's spec pairs, if present."""
    for spec in item.get("specs") or []:
        param = _clean(spec.get("parameter")).lower()
        if any(key in param for key in _PART_KEYS):
            value = _clean(spec.get("value"))
            if value:
                return value
    return None


def _format_quantity(item: Dict) -> str:
    """Format an item's quantity and unit as ``4 PC`` (trailing zeros stripped)."""
    qty = _clean(item.get("qty"))
    if qty:
        try:
            number = float(qty)
            qty = str(int(number)) if number.is_integer() else str(number)
        except ValueError:
            pass
    uom = _clean(item.get("uom")).split(":")[0].split(";")[0].strip()
    parts = [p for p in (qty, uom) if p]
    return " ".join(parts) or "as required"


class RFQEmailGenerator:
    """Builds a single request-for-quotation email covering all line items."""

    def __init__(self, signature: Optional[str] = None):
        """Store the signature block (explicit arg > RFQ_SIGNATURE env > default)."""
        self.signature = (signature or os.environ.get("RFQ_SIGNATURE") or DEFAULT_SIGNATURE).strip()

    def _subject(self, item: Dict) -> str:
        """Subject line for a single-item RFQ (includes the item code)."""
        name = _clean(item.get("item_name")) or _clean(item.get("description")) or "the item"
        code = _clean(item.get("item_number")) or _clean(item.get("item_no"))
        return f"Request for Quotation - {name}" + (f" ({code})" if code else "")

    def _item_block(self, item: Dict, index: Optional[int] = None,
                    include_destination: bool = False, destination: str = "") -> str:
        """Render one line item as a small labelled block of text."""
        name = _clean(item.get("item_name")) or _clean(item.get("description")) or "the item"
        raw_description = str(item.get("description") or "")
        # A multi-line description is really a spec blob; use the item name and
        # let the "Specifications:" line carry the detail instead.
        description = name if "\n" in raw_description else (_clean(raw_description) or name)
        code = _clean(item.get("item_number")) or _clean(item.get("item_no"))
        part = _find_part_number(item)
        lead = f"{index}. " if index else ""
        cont = "   " if index else ""

        lines = [f"{lead}Item Description: {description}"]
        if code:
            lines.append(f"{cont}Item Code / Ref: {code}")
        if part:
            lines.append(f"{cont}Part / Model Number: {part}")
        lines.append(f"{cont}Quantity Required: {_format_quantity(item)}")
        if include_destination:
            lines.append(f"{cont}Delivery Destination: {destination}")

        specs = item.get("specs") or []
        if specs:
            joined = "; ".join(
                f"{_clean(s.get('parameter'))}: {_clean(s.get('value'))}".rstrip(": ")
                for s in specs
                if _clean(s.get("parameter")) or _clean(s.get("value"))
            )
            if joined:
                lines.append(f"{cont}Specifications: {joined}")
        return "\n".join(lines)

    def build_email(self, items, meta: Optional[Dict] = None) -> Dict[str, str]:
        """Build one RFQ email (``subject`` + ``body``) covering all given items.

        Accepts a single item dict or a list of items. A single item keeps the
        sample's per-item layout; multiple items become a numbered list.
        """
        if isinstance(items, dict):
            items = [items]
        items = [item for item in (items or []) if item]
        meta = meta or {}
        destination = _clean(meta.get("delivery_location")) or "[delivery destination]"

        if len(items) == 1:
            subject = self._subject(items[0])
            heading = "We would like to request a formal quotation from your company for the following item:"
            block = self._item_block(items[0], include_destination=True, destination=destination)
        else:
            subject = f"Request for Quotation - {len(items)} Items"
            heading = "We would like to request a formal quotation from your company for the following items:"
            block = "\n\n".join(
                self._item_block(item, index=i + 1) for i, item in enumerate(items)
            )

        lines = [
            "Dear Sales Team,",
            "",
            heading,
            "",
            block,
            "",
            "Please refer to the attached document (Technical_Specifications) for full technical "
            "details and specifications.",
            "",
            "Kindly include the following in your quotation:",
            f"- Unit price and total commercial offer in MYR (delivered to {destination}).",
            "- Proposed model verification and technical datasheet.",
            f"- Estimated delivery lead time to {destination}.",
            "- Warranty coverage and local support terms in Malaysia.",
            "- Quotation validity period (minimum 30-60 days preferred).",
            "",
            "Please provide your best offer at your earliest convenience. If you have any questions, "
            "feel free to reply directly to this email.",
            "",
            "Thank you,",
            "",
            self.signature,
        ]
        return {"subject": subject, "body": "\n".join(lines)}

    def build_emails(self, data: Dict) -> List[Dict[str, str]]:
        """Return a single RFQ email covering every line item (empty if none)."""
        items = data.get("line_items") or []
        if not items:
            return []
        return [self.build_email(items, data.get("meta") or {})]
