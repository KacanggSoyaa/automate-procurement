#!/usr/bin/env python3
import click
from extractors.pdf_extractor import PDFExtractor
from processors.rfq_processor import RFQProcessor
from generators.enhanced_spec_sheet import EnhancedSpecSheetGenerator

@click.group()
def cli():
    """Automate Procurement Process - Enhanced"""
    pass

@cli.command()
@click.option('--itb-dir', default='./data/itb', help='Directory containing ITB files')
@click.option('--output', default='./outputs/spec_sheet_enhanced.docx', help='Output specification sheet path')
def extract(itb_dir, output):
    pdf_ext = PDFExtractor()
    results = pdf_ext.extract_itb_folder(itb_dir)
    all_content = '\n\n'.join([r.get('content', '') for r in results if not r.get('error')])
    processor = RFQProcessor()
    line_items = processor.extract_line_items_detailed(all_content)
    reqs = processor.extract_all_requirements(all_content)
    
    extracted_data = {
        'files_processed': len(results),
        'summary': f"Analyzed {len(results)} ITB documents from {itb_dir}",
        'line_items': line_items,
        'line_items_count': len(line_items),
        'technical_requirements': reqs['technical'],
        'submission_rules': reqs['submission'],
        'mandatory_requirements': reqs['mandatory'],
        'commercial_requirements': reqs['commercial'],
        'dates': reqs['dates']
    }
    gen = EnhancedSpecSheetGenerator()
    out = gen.generate(extracted_data, output)
    click.echo(f"Enhanced spec sheet generated: {out}")
    click.echo(f"Line items: {len(line_items)} | Files: {len(results)}")

if __name__ == '__main__':
    cli()
