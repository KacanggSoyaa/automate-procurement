# Automate Procurement Process

Automated system for RFQ/ITB procurement workflow with Python.

## Features

- **Step 1**: ITB Review & Line Item Extraction (PDF parsing)
- **Step 2**: Specification Sheet & Reference Document Generation (Word DOCX)
- **Step 3**: Vendor Sourcing & RFQ Dispatch (CSV management)

## Quick Start

1. Place your ITB/PDF files in data/itb/
2. Run the complete workflow:
   `ash
   python cli.py run-all
   `
3. Edit data/vendors/vendor_list.csv with vendor details
4. Dispatch RFQs:
   `ash
   python cli.py dispatch
   `

## Commands

- python cli.py analyze - Analyze ITB files
- python cli.py extract - Extract & generate spec sheet (Steps 1-2)
- python cli.py setup-vendors - Create vendor template
- python cli.py dispatch - Prepare RFQ dispatch package
- python cli.py run-all - Run complete workflow

## Output Files

- outputs/specification_sheet.docx - Generated spec sheet
- data/vendors/vendor_list.csv - Vendor database
- outputs/rfq_packages/rfq_summary.json - RFQ dispatch summary
