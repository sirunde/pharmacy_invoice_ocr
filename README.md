# RX Inventory Loader

RX Inventory Loader is a desktop tool designed to simplify pharmacy inventory data entry from invoices.

Instead of manually entering invoice line items, you can upload a PDF or CSV invoice, extract structured data
automatically, and quickly correct or confirm entries using a fast keyboard-driven overlay interface.

The goal is to reduce manual entry time and improve accuracy when importing inventory into RX systems.

## Features

- Upload and process CSV or PDF invoices
- Automatic data extraction from supported formats
- Fast editing overlay for quick corrections
- Keyboard-driven workflow optimized for pharmacy data entry
- Supports multiple distributor formats (Kinray, McKesson, etc.)
- Editable table view during runtime for real-time adjustments

## Tech Stack

- Python
- PyQt6 (GUI)
- pdfplumber (PDF parsing)
- pandas (CSV processing)
- Page dewarping utility from:
  https://github.com/mzucker/page_dewarp (modified for Python 3 compatibility)

> Note: EasyOCR was removed due to performance and executable size constraints.
>

## Supported Formats

- Kinray invoices (CSV)
- McKesson invoices (PDF)
- Smith (planned / not yet implemented)

## Workflow

1. Upload file
    - Select and upload a CSV or PDF invoice

2. Process data
    - CSV files are parsed using pandas
    - PDF files are parsed using pdfplumber
    - Custom parsing logic in parsers.py handles normalization and formatting

3. Data overlay
    - A floating table overlay appears for quick review and correction
    - Users can edit values directly or use keyboard shortcuts for faster entry

## Keyboard Shortcuts (Overlay Mode)

- PgUp → Paste NDC and submit
- End / PgDn → Paste date, quantity, and price in sequence
- F2 / Home → Move to next row
- Del → Move to previous row

You can also directly edit table cells while the system is running.

## Purpose

This tool is built to reduce manual data entry time and improve accuracy when importing pharmacy inventory into RX
systems.

It is actively being developed, and features are continuously being improved and expanded.