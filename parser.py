# import os
# import re
# import bisect
# import sys
# import traceback
#
# import cv2
# import numpy as np
#
# import pandas as pd
#
# try:
#     import page_dewarp
#
# except Exception:
#     page_dewarp = None
#
# COLUMNS = [
#     "LINE",
#     "ITEM",
#     "NDC",
#     "ORIG ORDER QTY",
#     "ORDER QTY",
#     "INVOICE QTY",
#     "OMIT CODE",
#     "UOM",
#     "DESCRIPTION",
#     "SIZE",
#     "FORM",
#     "CLASS",
#     "MSG",
#     "DEPT",
#     "UNIT PRICE",
#     "EXTENDED PRICE",
#     "NOTE CODE",
# ]
#
#
# FALLBACK_X = {
#     "LINE": 80,
#     "ITEM": 180,
#     "NDC": 295,
#     "ORIG ORDER QTY": 445,
#     "ORDER QTY": 557,
#     "INVOICE QTY": 653,
#     "OMIT CODE": 737,
#     "UOM": 805,
#     "DESCRIPTION": 900,
#     "SIZE": 1215,
#     "FORM": 1275,
#     "CLASS": 1405,
#     "MSG": 1510,
#     "DEPT": 1630,
#     "UNIT PRICE": 1815,
#     "EXTENDED PRICE": 1975,
#     "NOTE CODE": 2050,
# }
#
#
# _READER = None
#
# def get_base_dir():
#     if getattr(sys, "frozen", False):
#         # Running as PyInstaller exe
#         return os.path.dirname(sys.executable)
#     else:
#         # Running as normal .py
#         return os.path.dirname(os.path.abspath(__file__))
#
# def get_easyocr_model_dir():
#     return os.path.join(get_base_dir(), "easyocr_models")
#
# def get_reader():
#     global _READER
#
#     if _READER is None:
#         _READER = easyocr.Reader(
#             ["en"],
#             gpu=False,
#             model_storage_directory=get_easyocr_model_dir(),
#             user_network_directory=get_easyocr_model_dir(),
#             download_enabled=True,
#         )
#
#     return _READER
#
#
# def read_image(file_path):
#     if not file_path:
#         raise ValueError("No file path provided")
#
#     if not os.path.exists(file_path):
#         raise FileNotFoundError(f"File does not exist: {file_path}")
#
#     try:
#         data = np.fromfile(file_path, dtype=np.uint8)
#         img = cv2.imdecode(data, cv2.IMREAD_COLOR)
#     except Exception:
#         img = cv2.imread(file_path)
#
#     if img is None:
#         raise ValueError(f"OpenCV could not read image: {file_path}")
#
#     if img.size == 0:
#         raise ValueError(f"Image is empty: {file_path}")
#
#     return img
#
#
# def clean_tokens(raw_tokens):
#     out = []
#
#     for x, y, text in raw_tokens:
#         text = str(text).strip()
#
#         if text:
#             out.append((float(x), float(y), text))
#
#     return out
#
#
# def group_by_y(tokens, y_tol=17):
#     tokens = sorted(tokens, key=lambda t: (t[1], t[0]))
#     rows = []
#
#     for tok in tokens:
#         x, y, text = tok
#
#         if not rows:
#             rows.append({"y": y, "items": [tok]})
#             continue
#
#         if abs(y - rows[-1]["y"]) <= y_tol:
#             rows[-1]["items"].append(tok)
#             rows[-1]["y"] = float(np.median([i[1] for i in rows[-1]["items"]]))
#         else:
#             rows.append({"y": y, "items": [tok]})
#
#     return [(row["y"], sorted(row["items"], key=lambda t: t[0])) for row in rows]
#
#
# def cluster_x_positions(xs, x_tol=35):
#     xs = sorted(xs)
#     clusters = []
#
#     for x in xs:
#         if not clusters:
#             clusters.append([x])
#
#         elif abs(x - np.median(clusters[-1])) <= x_tol:
#             clusters[-1].append(x)
#
#         else:
#             clusters.append([x])
#
#     return [float(np.median(c)) for c in clusters]
#
#
# def build_column_anchors(header_tokens, max_snap_distance=45):
#     anchors = dict(FALLBACK_X)
#
#     if not header_tokens:
#         return [anchors[c] for c in COLUMNS]
#
#     header_xs = [x for x, y, text in header_tokens]
#
#     if not header_xs:
#         return [anchors[c] for c in COLUMNS]
#
#     clustered_xs = cluster_x_positions(header_xs)
#
#     for hx in clustered_xs:
#         nearest_col = min(COLUMNS, key=lambda c: abs(FALLBACK_X[c] - hx))
#
#         if abs(FALLBACK_X[nearest_col] - hx) <= max_snap_distance:
#             anchors[nearest_col] = 0.7 * FALLBACK_X[nearest_col] + 0.3 * hx
#
#     return [anchors[c] for c in COLUMNS]
#
#
# def make_boundaries(anchor_xs):
#     boundaries = [-float("inf")]
#
#     for i in range(len(anchor_xs) - 1):
#         boundaries.append((anchor_xs[i] + anchor_xs[i + 1]) / 2)
#
#     boundaries.append(float("inf"))
#
#     return boundaries
#
#
# def assign_column(x, boundaries):
#     idx = bisect.bisect_right(boundaries, x) - 1
#     idx = max(0, min(idx, len(COLUMNS) - 1))
#     return COLUMNS[idx]
#
#
# def extract_invoice_table(raw_tokens):
#     tokens = clean_tokens(raw_tokens)
#
#     if not tokens:
#         return pd.DataFrame(columns=COLUMNS)
#
#     gln_ys = [y for x, y, text in tokens if text.upper() == "GLN"]
#     gln_y = max(gln_ys) if gln_ys else 0
#
#     dlvry_ys = [
#         y
#         for x, y, text in tokens
#         if "DLVRY" in text.upper() and y > gln_y
#     ]
#
#     if not dlvry_ys:
#         first_dlvry_y = gln_y
#     else:
#         first_dlvry_y = min(dlvry_ys)
#
#     header_tokens = [
#         tok
#         for tok in tokens
#         if gln_y + 40 <= tok[1] <= first_dlvry_y - 5
#     ]
#
#     anchor_xs = build_column_anchors(header_tokens)
#     boundaries = make_boundaries(anchor_xs)
#
#     data_tokens = [
#         tok
#         for tok in tokens
#         if tok[1] > first_dlvry_y + 10
#     ]
#
#     grouped_rows = group_by_y(data_tokens, y_tol=17)
#
#     extracted_rows = []
#
#     for row_y, row_tokens in grouped_rows:
#         joined = " ".join(t[2] for t in row_tokens).upper()
#
#         if "TOTE" in joined or "DLVRY" in joined:
#             continue
#
#         row = {col: "" for col in COLUMNS}
#
#         for x, y, text in row_tokens:
#             col = assign_column(x, boundaries)
#             row[col] = f"{row[col]} {text}".strip()
#
#         has_item = bool(re.search(r"\d", row["ITEM"]))
#         has_ndc = bool(re.search(r"\d", row["NDC"]))
#         has_desc = bool(row["DESCRIPTION"].strip())
#
#         if has_item and has_ndc and has_desc:
#             extracted_rows.append(row)
#
#     return pd.DataFrame(extracted_rows, columns=COLUMNS)
#
#
# def safe_dewarp(img):
#     if page_dewarp is None:
#         return img
#
#     try:
#         test = page_dewarp.dewarp_image(img)
#
#         if test is None or test.size == 0:
#             return img
#
#         return test
#
#     except Exception:
#         traceback.print_exc()
#         return img
#
#
# def normalize_image(img):
#     if img is None or img.size == 0:
#         raise ValueError("Invalid image")
#
#     height, width = img.shape[:2]
#
#     if height > width:
#         img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
#
#     return img
#
#
# def parsing(file_path, progress_callback=None):
#     def progress(value):
#         if progress_callback:
#             try:
#                 progress_callback(value)
#             except Exception:
#                 pass
#
#     progress(15)
#
#     img = read_image(file_path)
#     img = normalize_image(img)
#
#     progress(25)
#
#     test = safe_dewarp(img)
#
#     if test is None or test.size == 0:
#         test = img
#
#     progress(35)
#
#     ocr = get_reader()
#
#     progress(45)
#
#     results = ocr.readtext(
#         test,
#         decoder="beamsearch",
#         beamWidth=2,
#         text_threshold=0.5,
#         low_text=0.3,
#         contrast_ths=0.05,
#         adjust_contrast=0.7,
#         min_size=10,
#         canvas_size=2560,
#         mag_ratio=1.8,
#         detail=1,
#     )
#
#     progress(80)
#
#     texts = []
#
#     for anchors, text, probability in results:
#         try:
#             cx = sum([anchor[0] for anchor in anchors]) / 4
#             cy = sum([anchor[1] for anchor in anchors]) / 4
#             texts.append((cx, cy, text))
#         except Exception:
#             continue
#
#     texts.sort(key=lambda x: (x[1], x[0]))
#
#     df = extract_invoice_table(texts)
#
#     progress(95)
#
#     return df
#
#
# if __name__ == "__main__":
#     df = parsing("kinray.jpg")
#     print(df)