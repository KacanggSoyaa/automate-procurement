import csv
from pathlib import Path
import json
from typing import Dict, List

class RFQDispatcher:
    def __init__(self, vendor_dir: str = './data/vendors'):
        self.vendor_dir = Path(vendor_dir)
        self.vendor_dir.mkdir(parents=True, exist_ok=True)
    
    def create_vendor_template(self, output_path: str = None):
        if not output_path:
            output_path = self.vendor_dir / 'vendor_list_template.csv'
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['vendor_id', 'company_name', 'contact_person', 'email', 'phone', 'category', 'notes'])
            writer.writerow(['V001', 'Sample Vendor Sdn Bhd', 'John Doe', 'john@sample.com', '012-3456789', 'General', 'Template'])
        return str(output_path)
    
    def load_vendors(self, csv_path: str = None):
        if not csv_path:
            csv_path = self.vendor_dir / 'vendor_list.csv'
        vendors = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    vendors.append(row)
        except Exception as e:
            pass
        return vendors
    
    def generate_rfq_package(self, spec_path: str, vendors: List[Dict], output_dir: str = './outputs/rfq_packages'):
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        package_info = {
            'spec_sheet': spec_path,
            'vendor_count': len(vendors),
            'packages': []
        }
        # Create RFQ summary
        rfq_summary = {
            'timestamp': __import__('datetime').datetime.now().isoformat(),
            'vendors': vendors,
            'spec_sheet': spec_path
        }
        summary_path = out_dir / 'rfq_summary.json'
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(rfq_summary, f, indent=2)
        package_info['summary_path'] = str(summary_path)
        return package_info
