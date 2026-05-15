import pdfplumber
import pandas as pd
import numpy as np
import os

all_tables = []


def kinray(text):
    a = text.find("NDC")
    rows = []

    if a > 0:
        for line in text[a:].split("\n"):
            items = line.split()

            if len(items) > 7:
                ndc = None
                qty = None
                price = None
                value = None

                if items[2][0].isdigit():
                    ndc = items[0]
                else:
                    continue
                if items[5][0].isdigit():
                    qty = float(items[5])
                else:
                    continue
                extended = False
                for i in items[-1::-1]:
                    try:
                        if not extended:
                            value = float(i.replace(",", ""))
                            extended_price = float(value)
                            extended = True
                        else:
                            value = float(i.replace(",", ""))
                            price = float(value)
                            break


                    except ValueError:
                        continue

                if price:
                    if(extended_price == qty*price):
                        rows.append((ndc, qty, price, extended_price))
                    else:
                        rows.append((ndc))

    return rows


def mck(text):
    a = text.find("NDC")
    rows = []
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
                    rows.append((ndc, qty, price, price * qty))

    return rows


def pdfParser(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        rows = []

        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            brand = text.find("CARDINAL")
            if brand >= 0:
                rows.extend(kinray(text))
            else:
                rows.extend(mck(text))

            columns = ["NDC", "QTY", "PRICE", "TOTAL_PRICE"]

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
    df.drop(
        columns=["INVOICE DATE", "INVOICE #", "Item#", "Order #", "Item Size", "Qty Ordered", "Previous Return Qty"],
        inplace=True,
        errors="ignore")
    df = df.rename(columns={
        'Qty Ship': 'QTY',
        'Cost ($)': 'PRICE',
        'Ext Cost ($) ': 'TOTAL_PRICE'
    })
    return df

if __name__ == "__main__":
    path = "kinray.pdf"
    a= pdfParser(path)