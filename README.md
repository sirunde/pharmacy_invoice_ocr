# RX Inventory Loader

This repository is designed to simplify the process of loading pharmacy inventory into RX.

Instead of manually entering invoice data, you can simply take a picture of your invoice and upload it into the GUI. The system uses **EasyOCR** to extract the data and allow fast editing and confirmation.

---

1. **Upload Image**
   - Take a picture of the invoice and upload it in the GUI.

2. **Run OCR**
   - The system uses EasyOCR to extract invoice data automatically.

3. **Start Overlay Editor**
   - A table overlay appears for fast manual correction and entry.

---

While editing the overlay:

- `PgUp` → Paste NDC
- `End` → Paste Quantity (uses invoiced QTY)
- `-` → Enter Price
- `=` → Move to next row

You can also directly edit the table while running, making it easy to quickly fix OCR errors or adjust values.

---

- Kinray invoices (currently supported)
- MCK (not yet)
- Smith (not yet)

---
## Working on
- Direct PDF import from distributor websites
- Improved OCR accuracy and invoice parsing
- Expanded inventory mapping automation

---
- Python
- EasyOCR
- PYQT6

---

## This tool is built to reduce manual data entry time and improve accuracy when importing inventory into RX systems. It is still under active development, and features are being expanded continuously.
~~if I am still working at the pharmacy~~