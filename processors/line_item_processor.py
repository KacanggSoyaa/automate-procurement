import re
from typing import Dict, List

class LineItemProcessor:
    def extract_line_items(self, text: str) -> List[Dict]:
        items = []
        # Look for common patterns in ITBs (item numbers, quantities, descriptions, codes)
        patterns = [
            r'(\d+)\s*[.\-]\s*(.+?)(?:\n|$)',
        ]
        # Try to find tables/numbered lists
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Pattern: number followed by description
            m = re.match(r'^(\d+)[\.\)]\s+(.{10,200})$', line)
            if m:
                items.append({
                    'item_no': m.group(1),
                    'description': m.group(2).strip(),
                    'raw': line
                })
        return items[:50]  # Limit for now

    def extract_requirements(self, text: str) -> Dict:
        reqs = {
            'technical': [],
            'submission_rules': [],
            'quantities': []
        }
        # Look for key terms
        for line in text.split('\n')[:200]:
            line_lower = line.lower()
            if any(k in line_lower for k in ['specification', 'technical', 'requirement']):
                reqs['technical'].append(line.strip())
            if any(k in line_lower for k in ['submit', 'deadline', 'due', 'closing']):
                reqs['submission_rules'].append(line.strip())
            if any(k in line_lower for k in ['qty', 'quantity', 'pcs', 'unit']):
                reqs['quantities'].append(line.strip())
        return reqs
