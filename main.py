#!/usr/bin/env python3
import click
from pathlib import Path
from extractors.pdf_extractor import PDFExtractor
from processors.line_item_processor import LineItemProcessor
from generators.spec_sheet_generator import SpecSheetGenerator

@click.group()
def cli():
    """Automate Procurement Process - RFQ/ITB Automation"""
    pass

@cli.command()
@click.option('--itb-dir', default='./data/itb', help='Directory containing ITB files')
@click.option('--output', default='./outputs/spec_sheet.docx', help='Output specification sheet path')
def extract(itb_dir, output):
    """Step 1 & 2: Extract from ITB and generate specification sheet"""
    click.echo(f"Extracting ITB from: {itb_dir}")
    pdf_ext = PDFExtractor()
    results = pdf_ext.extract_itb_folder(itb_dir)
    all_content = '\n\n'.join([r.get('content', '') for r in results if not r.get('error')])
    processor = LineItemProcessor()
    line_items = processor.extract_line_items(all_content)
    reqs = processor.extract_requirements(all_content)
    extracted_data = {
        'files_processed': len(results),
        'line_items': line_items,
        'line_items_count': len(line_items),
        'technical_requirements': reqs['technical'][:20],
        'submission_rules': reqs['submission_rules'][:20],
        'quantities': reqs['quantities'][:20]
    }
    generator = SpecSheetGenerator()
    out_path = generator.generate_spec_sheet(extracted_data, output)
    click.echo(f"Specification sheet generated: {out_path}")
    click.echo(f"  - Line items: {len(line_items)}")
    click.echo(f"  - Files processed: {len(results)}")

if __name__ == '__main__':
    cli()
