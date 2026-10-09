#!/usr/bin/env python3
"""Command-line entry point for the Automate Procurement workflow.

Mirrors the web backend: reads a folder of ITB PDFs (and screenshots),
classifies them with Gemini and writes a formatted RFQ specification sheet.
"""
import click
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from extractors.pdf_extractor import PDFExtractor
from processors.ai_processor import AIProcessor
from generators.enhanced_spec_sheet import EnhancedSpecSheetGenerator
from generators.rfq_dispatcher import RFQDispatcher


@click.group()
def cli():
    """Automate Procurement Process CLI.

    Step 1: ITB Review & Line Item Extraction
    Step 2: Specification Sheet & Reference Document Generation
    Step 3: Vendor Sourcing & RFQ Dispatch
    """
    pass


@cli.command()
@click.option('--itb-dir', default='./data/itb', help='Directory containing ITB files')
@click.option('--output', default='./outputs/specification_sheet.docx', help='Output spec sheet path')
@click.option('--pattern', default='*ITB*', help='Filename glob of source PDFs (default: *ITB*)')
@click.option('--images', default=None, help='Comma-separated image globs to include (default: png/jpg/jpeg/webp/bmp)')
@click.option('--no-images', is_flag=True, help='Do not send images to Gemini')
@click.option('--model', default=None, help='Gemini model (default: gemini-3.8-flash)')
@click.option('--skip', default='', help='Comma-separated exact filenames to exclude from extraction')
def extract(itb_dir, output, pattern, images, no_images, model, skip):
    """Steps 1 & 2: extract ITB content and generate the spec sheet."""
    click.echo('Step 1: ITB Review & Line Item Extraction...')
    pdf_ext = PDFExtractor()
    results = pdf_ext.extract_itb_folder(itb_dir, pattern=pattern)
    if not results:
        raise click.ClickException(f'No PDFs matching "{pattern}" found in {itb_dir}')

    # Every PDF is read by default; only exact filenames listed here are skipped.
    skip_set = {s.strip().lower() for s in skip.split(',') if s.strip()}
    ok = [r for r in results if not r.get('error')]
    docs = [r for r in ok if r['filename'].strip().lower() not in skip_set]
    for r in ok:
        if r['filename'].strip().lower() in skip_set:
            click.echo(f'  - skipping (settings): {r["filename"]}')
    source_files = [r['filename'] for r in ok]
    click.echo(f'  - {len(results)} file(s) matched "{pattern}"')
    all_content = '\n\n'.join([r.get('content', '') for r in docs])

    # Collect standalone screenshots and render image-heavy PDF pages so the
    # model can read tables/specs that exist only as pictures.
    image_paths = []
    if not no_images:
        globs = [g.strip() for g in images.split(',')] if images else None
        images_found = pdf_ext.collect_image_files(itb_dir, patterns=globs)
        image_paths += images_found
        source_files += [Path(p).name for p in images_found]
        for r in docs:
            image_paths += pdf_ext.render_image_pages(r['path'], './outputs/extracted_images')
        if image_paths:
            click.echo(f'  - {len(image_paths)} image(s) will be sent to Gemini')

    click.echo('Classifying content with Gemini (separating line items from requirements)...')
    try:
        processor = AIProcessor(model=model)
    except RuntimeError as e:
        raise click.ClickException(str(e))
    reqs = processor.classify(
        all_content,
        image_paths=image_paths,
        progress=lambda kind, i, n: click.echo(f'  - classifying {kind} {i}/{n}'),
    )

    # Assemble the data structure consumed by the DOCX generator.
    line_items = reqs['line_items']
    extracted_data = {
        'files_processed': len(results),
        'summary': f'Analyzed {len(results)} ITB documents from {itb_dir}',
        'source_files': source_files,
        'meta': reqs.get('meta', {}),
        'line_items': line_items,
        'line_items_count': len(line_items),
        'technical_requirements': reqs['technical'],
        'submission_rules': reqs['submission'],
        'mandatory_requirements': reqs['mandatory'],
        'commercial_requirements': reqs['commercial'],
        'dates': reqs['dates']
    }
    click.echo('Step 2: Generating specification sheet...')
    gen = EnhancedSpecSheetGenerator()
    out = gen.generate(extracted_data, output)
    click.echo(click.style(f'Done: {out}', fg='green'))
    click.echo(f'  - Files processed: {len(results)}')
    click.echo(f'  - Line items extracted: {len(line_items)}')
    click.echo(f'  - Technical reqs: {len(reqs["technical"])}')
    click.echo(f'  - Submission rules: {len(reqs["submission"])}')


@cli.command()
def setup_vendors():
    """Step 3a: create the vendor CSV template used for RFQ dispatch."""
    d = RFQDispatcher()
    p = d.create_vendor_template()
    click.echo(click.style(f'Vendor template created: {p}', fg='green'))
    click.echo('Edit vendor_list.csv with your actual vendor data')


@cli.command()
@click.option('--spec-sheet', default='./outputs/specification_sheet.docx', help='Path to spec sheet')
@click.option('--vendor-file', default='./data/vendors/vendor_list.csv', help='Vendor CSV file')
def dispatch(spec_sheet, vendor_file):
    """Step 3b: build an RFQ dispatch package for the loaded vendors."""
    d = RFQDispatcher()
    vendors = d.load_vendors(vendor_file)
    if not vendors:
        click.echo(click.style(f'No vendors found in {vendor_file}. Run setup-vendors first.', fg='yellow'))
        return
    pkg = d.generate_rfq_package(spec_sheet, vendors)
    click.echo(click.style('RFQ package prepared', fg='green'))
    click.echo(f'  - Vendors: {len(vendors)}')
    click.echo(f'  - Summary: {pkg["summary_path"]}')


@cli.command()
@click.option('--itb-dir', default='./data/itb')
@click.option('--pattern', default='*ITB*', help='Filename glob of source PDFs (default: *ITB*)')
def analyze(itb_dir, pattern):
    """Quickly report which PDFs match and how much text was read from each."""
    pdf_ext = PDFExtractor()
    results = pdf_ext.extract_itb_folder(itb_dir, pattern=pattern)
    for r in results:
        if r.get('error'):
            click.echo(click.style(f'{r["filename"]}: {r["error"]}', fg='red'))
        else:
            click.echo(click.style(f'{r["filename"]}: {r["size"]} chars', fg='green'))


@cli.command()
def run_all():
    """Run extraction and vendor setup back-to-back as one workflow."""
    extract.callback(itb_dir='./data/itb', output='./outputs/specification_sheet.docx',
                     pattern='*ITB*', images=None, no_images=False, model=None, skip='')
    setup_vendors.callback()
    click.echo(click.style('\nWorkflow complete!', fg='green'))


if __name__ == '__main__':
    cli()
