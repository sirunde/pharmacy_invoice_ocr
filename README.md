# RX Inventory Loader

A Python desktop application for extracting pharmacy invoice line items and streamlining inventory entry into pharmacy management systems.

The application combines distributor specific invoice parsing, an editable PyQt6 interface, and global keyboard shortcuts to reduce repetitive data entry and make invoice processing faster.

## Supported Distributors

| Distributor | Input format | Parser |
|---|---|---|
| Kinray | CSV and PDF | `csvParser()` and `kinray()` |
| McKesson | PDF | `mck()` |
| Smith | PDF | `smith()` |

## Features

- **Multi distributor invoice processing:** Handles Kinray, McKesson, and Smith invoice formats.
- **PDF text extraction:** Uses `pdfplumber` to extract invoice text and identify supported distributor layouts.
- **CSV normalization:** Processes Kinray CSV data, standardizes NDC values, and maps quantity and cost fields to a common structure.
- **Invoice data validation:** Checks extracted values and compares line totals against quantity multiplied by unit price where implemented.
- **Interactive desktop interface:** Provides a PyQt6 interface for reviewing and editing extracted inventory data.
- **Keyboard driven entry:** Copies selected invoice fields to the clipboard and pastes them into the active pharmacy application.
- **Error logging:** Records application errors in a log file to help troubleshoot processing issues.
- **Document preprocessing utilities:** Includes a modified page dewarping utility for image correction workflows.

## Technology Stack

- Python
- PyQt6
- pandas
- pdfplumber
- NumPy
- keyboard
- pyperclip
- pyautogui
- Decimal arithmetic for monetary and quantity calculations

## Project Structure

```text
pharmacy_invoice_ocr/
├── main.py           # Desktop application and inventory entry workflow
├── parser.py         # Additional and legacy invoice parsing logic
├── parsers.py        # Distributor-specific PDF and CSV parsers
├── hotkey.py         # Global keyboard shortcut controller
├── page_dewarp.py    # Document image dewarping utility
└── test.pdf          # Sample PDF for testing
```

## How It Works

### 1. Load an invoice

Choose a supported invoice file through the desktop application.

- Kinray invoices can be processed from CSV or PDF.
- McKesson invoices are processed from PDF.
- Smith invoices are processed from PDF.

### 2. Extract and normalize invoice data

The parsing module converts supported invoice records into a common tabular structure.

The normalized fields include:

| Field | Description |
|---|---|
| `NDC` | National Drug Code |
| `QTY` | Invoice quantity |
| `PRICE` | Unit price |
| `TOTAL_PRICE` | Extended line price |

The CSV parser also standardizes NDC values to 11 characters and renames distributor specific quantity and cost columns.

### 3. Review and correct the results

The desktop interface provides an editable table for inspecting the extracted information and correcting values before entering them into the pharmacy system.

### 4. Transfer data using keyboard shortcuts

The keyboard controller uses the clipboard and simulated keyboard input to paste selected fields into the active application. This avoids repeatedly copying individual values by hand.

## Installation

### Requirements

- Python 3
- A desktop environment supported by PyQt6
- Access to the target pharmacy application
- Appropriate permissions for global keyboard shortcuts and simulated input

Clone the repository:

```bash
git clone https://github.com/sirunde/pharmacy_invoice_ocr.git
cd pharmacy_invoice_ocr
```

Install the Python dependencies:

```bash
python -m pip install PyQt6 pandas numpy pdfplumber keyboard pyperclip pyautogui
```

The `page_dewarp.py` utility may require additional dependencies depending on the preprocessing path being used.

## Run the Application

Launch the desktop application:

```bash
python main.py
```

Select a supported invoice, review the extracted data, correct any errors, and use the application's data entry workflow to transfer the required fields into the pharmacy system.

## Global Keyboard Shortcuts

The standalone controller in `hotkey.py` registers the following shortcuts:

| Shortcut | Action |
|---|---|
| `Page Up` | Paste the current row's NDC |
| `End` | Paste the current row's invoice quantity |
| `-` | Paste the current row's unit price |
| `=` | Advance to the next row |

These shortcuts use clipboard operations and simulated `Ctrl+V` input. The active application must have focus in the appropriate field before a value is pasted.

The main application's interface may have additional controls or shortcuts.

## Error Handling and Troubleshooting

The application configures error logging under:

```text
logs/Invoices/app.log
```

If an invoice fails to process:

1. Confirm that the file is readable and uses a supported distributor format.
2. Check that the PDF contains extractable text if using the PDF parser.
3. Verify the extracted NDC, quantity, and price values.
4. Review the application log for error details.
5. Compare the results against the original invoice before entering inventory.

## Important Notes

- Invoice parsing relies on distributor specific text patterns and layouts. Changes to invoice formatting may require parser updates.
- Incorrectly extracted values should be corrected before they are entered into the pharmacy system.
- Global keyboard shortcuts can interact with other applications. Ensure the intended pharmacy application and input field are active before pasting.
- Do not use extracted values as a substitute for reviewing the original invoice.

## Acknowledgments

The project includes a modified version of the [page_dewarp](https://github.com/mzucker/page_dewarp) utility for document image preprocessing.

## License

Refer to the repository and dependency licensing terms before redistributing this application.
