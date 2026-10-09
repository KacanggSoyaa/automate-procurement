"""Reference example of the exact RFQ layout the generator should match.

This is a standalone script (it runs and writes a sample DOCX when executed)
and is kept only as a formatting reference for ``enhanced_spec_sheet.py``.
It is not imported by the application.
"""
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

doc = docx.Document()

# Page Setup - Margins matching standard docx setup
for section in doc.sections:
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)

# Colors matching the exact Teal corporate style from Technical_Specifications.docx
PRIMARY_COLOR = RGBColor(0, 128, 128)      # Teal #008080
SECONDARY_COLOR = RGBColor(51, 51, 51)    # Dark Charcoal #333333
MUTED_TEXT = RGBColor(100, 100, 100)      # Gray
HEADER_BG = "008080"                       # Teal Header fill
ALT_ROW_BG = "F4F8F8"                      # Light tint

def set_cell_background(cell, hex_color):
    """Fill a table cell with a solid background colour."""
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Apply internal padding (in dxa twips) to a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def add_heading_styled(doc, text, level):
    """Add a level 1/2 heading with the corporate font and colour."""
    h = doc.add_heading(level=level)
    run = h.add_run(text)
    run.font.name = 'Calibri'
    if level == 1:
        run.font.size = Pt(15)
        run.font.bold = True
        run.font.color.rgb = PRIMARY_COLOR
        h.paragraph_format.space_before = Pt(14)
        h.paragraph_format.space_after = Pt(6)
    elif level == 2:
        run.font.size = Pt(12)
        run.font.bold = True
        run.font.color.rgb = SECONDARY_COLOR
        h.paragraph_format.space_before = Pt(10)
        h.paragraph_format.space_after = Pt(4)
    return h

# Document Title
title_p = doc.add_paragraph()
title_run = title_p.add_run("REQUEST FOR QUOTATION (RFQ)")
title_run.font.name = 'Calibri'
title_run.font.size = Pt(18)
title_run.font.bold = True
title_run.font.color.rgb = PRIMARY_COLOR
title_p.paragraph_format.space_after = Pt(2)

subtitle_p = doc.add_paragraph()
sub_run = subtitle_p.add_run("Technical Specifications & Item Requirement Schedule")
sub_run.font.name = 'Calibri'
sub_run.font.size = Pt(11)
sub_run.font.italic = True
sub_run.font.color.rgb = MUTED_TEXT
subtitle_p.paragraph_format.space_after = Pt(12)

# Top Metadata Block Table (Exact layout from Technical_Specifications.docx)
meta_table = doc.add_table(rows=2, cols=2)
meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
meta_table.autofit = False

meta_data = [
    ("Project / Ref: 51019271 - SUPPLY AND DELIVERY OF HARD DISK DRIVE", "Delivery Location: PETRONAS Chemicals Methanol, Labuan"),
    ("Document Type: Technical Specification Sheet", "Target Delivery: To be specified")
]

for row_idx, (col1, col2) in enumerate(meta_data):
    row = meta_table.rows[row_idx]
    
    cell_left = row.cells[0]
    cell_left.width = Inches(3.8)
    set_cell_background(cell_left, "F0F4F4")
    set_cell_margins(cell_left, top=80, bottom=80, left=120, right=120)
    p_l = cell_left.paragraphs[0]
    r_l = p_l.add_run(col1)
    r_l.font.name = 'Calibri'
    r_l.font.bold = True
    r_l.font.size = Pt(9.5)
    p_l.paragraph_format.space_after = Pt(1)
    
    cell_right = row.cells[1]
    cell_right.width = Inches(3.0)
    set_cell_background(cell_right, "F0F4F4")
    set_cell_margins(cell_right, top=80, bottom=80, left=120, right=120)
    p_r = cell_right.paragraphs[0]
    r_r = p_r.add_run(col2)
    r_r.font.name = 'Calibri'
    r_r.font.bold = True
    r_r.font.size = Pt(9.5)
    p_r.paragraph_format.space_after = Pt(1)

doc.add_paragraph().paragraph_format.space_after = Pt(8)

# Section 1: Summary of Required Items Table
add_heading_styled(doc, "1. Summary of Required Items", level=1)

summary_table = doc.add_table(rows=2, cols=5)
summary_table.alignment = WD_TABLE_ALIGNMENT.CENTER
summary_table.autofit = False

headers = ["No.", "Item Name", "Item Number", "Description & Key Specs", "Qty", "UOM"]
col_widths = [Inches(0.5), Inches(1.8), Inches(1.1), Inches(2.5), Inches(0.5), Inches(0.4)]

# Table Header
hdr_cells = summary_table.rows[0].cells
for idx, text in enumerate(["No.", "Item Name", "Item Number", "Description & Key Specs", "Qty", "UOM"]):
    hdr_cells[idx].width = col_widths[idx]
    set_cell_background(hdr_cells[idx], HEADER_BG)
    set_cell_margins(hdr_cells[idx], top=80, bottom=80, left=80, right=80)
    p = hdr_cells[idx].paragraphs[0]
    r = p.add_run(text)
    r.font.name = 'Calibri'
    r.font.bold = True
    r.font.size = Pt(9.5)
    r.font.color.rgb = RGBColor(255, 255, 255)

# Row 1 Data
row1_cells = summary_table.rows[1].cells
row1_data = [
    "1",
    "DISC DRIVE, MAG, WD10EZEX, HRD DISC, SATA",
    "51019271",
    "1TB 3.5\" SATA 6Gb/s 7200 RPM Internal Hard Disk Drive (Western Digital WD10EZEX)",
    "5",
    "PC"
]

for idx, text in enumerate(row1_data):
    row1_cells[idx].width = col_widths[idx]
    set_cell_background(row1_cells[idx], "FFFFFF")
    set_cell_margins(row1_cells[idx], top=70, bottom=70, left=80, right=80)
    p = row1_cells[idx].paragraphs[0]
    r = p.add_run(text)
    r.font.name = 'Calibri'
    r.font.size = Pt(9.5)
    if idx in [0, 2, 4, 5]:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_paragraph().paragraph_format.space_after = Pt(10)

# Section 2: Detailed Technical Specifications
add_heading_styled(doc, "2. Detailed Technical Specifications", level=1)

add_heading_styled(doc, "Item 1: Internal Hard Disk Drive (1TB)", level=2)

specs_list = [
    ("Item Name", "DISC DRIVE, MAG, WD10EZEX, HRD DISC, SATA"),
    ("Item Number", "51019271"),
    ("Manufacturer Name", "WESTERN DIGITAL"),
    ("Manufacturer Part Number", "WD10EZEX"),
    ("Storage Capacity", "1TB (1000 GB)"),
    ("Form Factor / Type", "3.5-inch Internal Hard Disk Drive (HDD)"),
    ("Interface / Connectivity", "SATA 6 Gb/s (PATA 100 MB/s compatibility)"),
    ("Rotational Speed", "7,200 RPM"),
    ("Cache Memory", "64 MB"),
    ("Data Transfer Rate (Max)", "Buffer to Host: 6 Gb/s | Host to/from Drive (Sustained): 150 MB/s"),
    ("Power Supply", "12 VDC (+/-10%), 2.5 A Peak"),
    ("Environmental / Standard", "RoHS Compliant"),
    ("Quantity Required", "5 Units")
]

for param, val in specs_list:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.left_indent = Inches(0.2)
    
    r_p = p.add_run(f"{param}: ")
    r_p.font.name = 'Calibri'
    r_p.font.bold = True
    r_p.font.size = Pt(10)
    
    r_v = p.add_run(val)
    r_v.font.name = 'Calibri'
    r_v.font.size = Pt(10)

doc.add_paragraph().paragraph_format.space_after = Pt(10)

# Section 3: Quotation Submission Instructions
add_heading_styled(doc, "3. Quotation Submission Instructions", level=1)

instructions = [
    "Please provide unit price and total pricing in MYR delivered to PETRONAS Chemicals Methanol, Labuan.",
    "Include official manufacturer datasheets or technical compliance verification for the proposed model.",
    "Specify the lead time / estimated delivery date to PETRONAS Chemicals Methanol, Labuan.",
    "State the standard manufacturer warranty period and warranty support terms in Malaysia.",
    "Ensure quotation validity is a minimum of 30 to 60 days from submission date."
]

for inst in instructions:
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(inst)
    r.font.name = 'Calibri'
    r.font.size = Pt(10)

file_path = "RFQ_Specification_Sheet_Exact_Format.docx"
doc.save(file_path)

print(f"File created successfully: {file_path}")