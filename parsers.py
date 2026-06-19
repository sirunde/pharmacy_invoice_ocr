import pdfplumber
import pandas as pd
import numpy as np
import os
from decimal import Decimal, InvalidOperation
import re

all_tables = []


def kinray(text):
    a = text.find("NDC")
    rows = []

    if a > 0:
        for line in text[a:].split("\n"):
            items = line.split()

            if len(items) > 7:
                try:
                    ndc = None
                    qty = None
                    price = None
                    value = None
                    extended_price = None

                    if items[2][0].isdigit():
                        ndc = items[2]
                        if '-' not in ndc and ndc.isdigit():
                            ndc = f"{ndc[:5]}-{ndc[5:9]}-{ndc[9:]}"
                    else:
                        continue

                    if items[5][0].isdigit():
                        raw_qty = items[5]
                        clean_qty = re.sub(r'\D', '', raw_qty)
                        qty = Decimal(clean_qty)
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
                except:
                    rows.append((ndc, 0, 0, 0))

    return rows


def mck(text):
    a = text.find("NDC")
    rows = []
    if a > 0:
        for line in text[a:].split("\n"):
            items = line.split()

            if len(items) > 7:
                try:
                    ndc = None
                    qty = None
                    price = None
                    extended_price = None

                    if items[0][0].isdigit():
                        ndc = items[0]
                        if '-' not in ndc and ndc.isdigit():
                            ndc = f"{ndc[:5]}-{ndc[5:9]}-{ndc[9:]}"
                    else:
                        continue

                    if items[3][0].isdigit():
                        raw_qty = items[3]

                        clean_qty = re.sub(r'\D', '', raw_qty)
                        qty = Decimal(clean_qty)
                    else:
                        continue

                    try:
                        R = items.index("R")
                        try:
                            price = Decimal(items[R + 1].replace(",", ""))

                            try:
                                K = items.index("K")
                                extended_price = Decimal(items[K + 1].replace(",", ""))

                            except:
                                extended_price = Decimal(items[R + 2].replace(",", ""))

                        except (InvalidOperation):
                            continue

                        except Exception as e:
                            raise RuntimeError("errors") from e

                        if price is not None and qty is not None and ndc is not None:
                            if extended_price == qty * price:
                                rows.append((ndc, qty, price, extended_price))
                            else:
                                rows.append((ndc, qty, 0))
                    except:
                        continue
                except:
                    rows.append((ndc, 0, 0, 0))

    return rows


def smith(text):
    a = text.find("Rx")
    rows = []
    if a > 0:
        for line in text[a:].split("\n"):
            items = line.split()
            if len(items) > 7:
                try:
                    ndc = None
                    qty = None
                    price = None
                    rx = False
                    extended = False
                    extended_price = None

                    if items[1][0].isdigit():
                        raw_qty = items[1]
                        clean_qty = re.sub(r'\D', '', raw_qty)
                        qty = Decimal(clean_qty)

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
                                    if '-' not in ndc and ndc.isdigit():
                                        ndc = f"{ndc[:5]}-{ndc[5:9]}-{ndc[9:]}"
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
                except:
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
    path = "errors.pdf"
    a = pdfParser(path)
    print(a)
