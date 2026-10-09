import re
from typing import Dict, List

class RFQProcessor:
    def extract_line_items_detailed(self, text: str) -> List[Dict]:
        items = []
        # Look for table-like patterns and structured line items
        lines = text.split('\n')
        current_item = None
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            # Match item number patterns
            m = re.match(r'^(\d{1,3})[\.\)]\s+(.+)$', line)
            if m and len(m.group(2)) > 5:
                if current_item:
                    items.append(current_item)
                current_item = {
                    'item_no': m.group(1),
                    'description': m.group(2),
                    'details': [],
                    'qty': None,
                    'unit': None,
                    'code': None
                }
            elif current_item and len(line) > 0:
                # Look for qty/unit patterns
                qty_m = re.search(r'(qty|quantity|qte)\s*:?\s*(\d+)', line.lower())
                if qty_m:
                    current_item['qty'] = qty_m.group(2)
                unit_m = re.search(r'(unit|each|pcs|set|lot)\b', line.lower())
                if unit_m:
                    current_item['unit'] = unit_m.group(1)
                code_m = re.search(r'(code|part|item\s*no|material)\s*:?\s*([A-Z0-9\-_]+)', line, re.I)
                if code_m:
                    current_item['code'] = code_m.group(2)
                if len(line) < 100:  # Short detail lines
                    current_item['details'].append(line)
        if current_item:
            items.append(current_item)
        return items[:100]

    def extract_all_requirements(self, text: str) -> Dict:
        reqs = {
            'technical': [],
            'commercial': [],
            'submission': [],
            'mandatory': [],
            'dates': [],
            'contact': []
        }
        for line in text.split('\n'):
            line_clean = line.strip()
            if not line_clean or len(line_clean) < 3:
                continue
            l = line_clean.lower()
            if any(k in l for k in ['spec', 'technical', 'requirement', 'description', 'material', 'dimension']):
                reqs['technical'].append(line_clean)
            if any(k in l for k in ['price', 'commercial', 'cost', 'currency', 'tax', 'payment']):
                reqs['commercial'].append(line_clean)
            if any(k in l for k in ['submit', 'submission', 'bid', 'proposal', 'closing', 'deadline', 'due date']):
                reqs['submission'].append(line_clean)
            if any(k in l for k in ['mandatory', 'compulsory', 'must submit']):
                reqs['mandatory'].append(line_clean)
            if re.search(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}', line_clean):
                reqs['dates'].append(line_clean)
        return reqs
