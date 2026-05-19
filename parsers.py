import pdfplumber
import pandas as pd
import numpy as np
import os
from decimal import Decimal, InvalidOperation

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
                extended_price = None
                if items[2][0].isdigit():
                    ndc = items[2]
                else:
                    continue
                if items[5][0].isdigit():
                    qty = Decimal((items[5]))
                else:
                    continue
                extended = False
                for i in reversed(items):
                    try:
                        value = Decimal(i.replace(",", ""))

                        if not extended:
                            extended_price = value
                            extended = True
                        else:
                            price = value
                            break


                    except (InvalidOperation):
                        continue

                    except Exception as e:
                        raise RuntimeError("errors") from e

                if price is not None and qty is not None and ndc is not None:
                    if extended_price == qty * price:
                        rows.append((ndc, qty, price, extended_price))
                    else:
                        rows.append((ndc, 0, 0, 0))

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
                extended_price = None

                if items[0][0].isdigit():
                    ndc = items[0]
                else:
                    continue
                if items[3][0].isdigit():
                    qty = Decimal((items[3]))
                else:
                    continue
                extended = False

                for i in reversed(items):
                    try:
                        value = Decimal(i.replace(",", ""))

                        if not extended:
                            extended_price = value
                            extended = True
                        else:
                            price = value
                            break


                    except (InvalidOperation):
                        continue

                    except Exception as e:
                        raise RuntimeError("errors") from e

                if price is not None and qty is not None and ndc is not None:
                    if extended_price == qty * price:
                        rows.append((ndc, qty, price, extended_price))
                    else:
                        rows.append((ndc, 0, 0, 0))

    return rows


def smith(text):
    a = text.find("Rx")
    rows = []
    if a > 0:
        for line in text[a:].split("\n"):
            items = line.split()
            if len(items) > 7:
                ndc = None
                qty = None
                price = None
                rx = False
                extended = False
                extended_price = None

                if items[1][0].isdigit():
                    qty = Decimal((items[1]))

                for i in reversed(items):
                    try:
                        value = Decimal(i.replace(",", ""))

                        if not extended:
                            extended_price = value
                            extended = True
                        else:

                            if (not rx and not price):
                                price = value
                            if (rx):
                                ndc = i
                                break

                    except (InvalidOperation):
                        if (i == "RX"):
                            rx = True
                        continue
                    except Exception as e:
                        raise RuntimeError("errors") from e

                if price is not None and rx and qty is not None:
                    if extended_price == qty * price:
                        rows.append((ndc, qty, price, extended_price))
                    else:
                        rows.append((ndc, 0, 0, 0))

    return rows


def pdfParser(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        rows = []

        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()

            if text.find("CARDINAL") >= 0:
                rows.extend(kinray(text))
            elif text.find("MCKESSON") >= 0:
                rows.extend(mck(text))
            elif text.find("BURLINGTON") >= 0:
                rows.extend(smith(text))

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
    path = "smith.pdf"
    a = pdfParser(path)
    print(a)
