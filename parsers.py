import pdfplumber
import pandas as pd
import numpy as np
import os

all_tables = []


def pdfParser(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        rows = []

        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()

            a = text.find("NDC")

            columns = ["NDC", "QTY", "PRICE","TOTAL_PRICE"]
            if a > 0:
                for line in text[a:].split("\n"):
                    items = line.split()

                    if len(items) > 7:
                        ndc = None
                        qty = None
                        price = None

                        if items[0][0].isdigit():
                            ndc = items[0]
                        else:
                            continue
                        if items[3][0].isdigit():
                            qty = float(items[3])
                        else:
                            continue
                        for i in items[-2::-1]:
                            try:
                                value = float(i.replace(",", ""))
                                price = float(value)
                                break
                            except ValueError:
                                continue
                        if price:
                            rows.append((ndc, qty, price,price*qty))

            else:
                continue

            # first row = columns
        df = pd.DataFrame(rows, columns=columns)
    return df

def csvParser(csv_path):
    if not csv_path:
        raise ValueError("No file path provided")

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"File does not exist: {csv_path}")

    df = pd.read_csv(csv_path)
    df["NDC"] = df["NDC"].astype(str).str.zfill(11)
    # hard coded one. If it is not Kinray may errors occur
    df.drop(columns=["INVOICE DATE", "INVOICE #", "Item#", "Order #","Item Size","Qty Ordered" ,"Previous Return Qty"], inplace=True,
                 errors="ignore")
    df = df.rename(columns={
        'Qty Ship':'QTY',
        'Cost ($)': 'PRICE',
        'Ext Cost ($) ': 'TOTAL_PRICE'
    })
    return df
