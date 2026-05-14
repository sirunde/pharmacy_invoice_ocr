import sys
import os
import logging
import traceback
import time
import functools
import threading
from datetime import datetime

import pandas as pd
import keyboard
import pyperclip
import pyautogui

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QProgressBar,
    QLineEdit,
)

from parsers import pdfParser, csvParser


# ================= LOGGING =================

def setup_logging():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(base_dir, "logs", "Invoices")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "app.log")

    logging.basicConfig(
        filename=log_file,
        level=logging.ERROR,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    return log_file


LOG_FILE = setup_logging()

# ================= SAFE ERROR NOTIFIER =================

ERROR_NOTIFIER = None


class ErrorNotifier(QObject):
    error = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.error.connect(self.show_error)

    def show_error(self, title, message):
        try:
            short_message = message

            if len(short_message) > 3000:
                short_message = short_message[:3000] + "\n\n... message truncated. See log file."

            QMessageBox.critical(
                None,
                title,
                f"{short_message}\n\nLog file:\n{LOG_FILE}"
            )
        except Exception:
            pass


def notify_error(title, message):
    try:
        logging.error("%s\n%s", title, message)
    except Exception:
        pass

    try:
        if ERROR_NOTIFIER is not None:
            ERROR_NOTIFIER.error.emit(title, message)
    except Exception:
        pass


def safe_call(title="Error"):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception:
                err = traceback.format_exc()
                notify_error(title, err)
                return None

        return wrapper

    return decorator


def global_exception_hook(exc_type, exc_value, exc_traceback):
    try:
        error_text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        notify_error("Unexpected Error", error_text)
    except Exception:
        pass


def global_thread_exception_hook(args):
    try:
        error_text = "".join(
            traceback.format_exception(
                args.exc_type,
                args.exc_value,
                args.exc_traceback
            )
        )
        notify_error("Thread Error", error_text)
    except Exception:
        pass


sys.excepthook = global_exception_hook
threading.excepthook = global_thread_exception_hook


# ================= PARSER WORKER =================

class ParserWorker(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            self.progress.emit(10)

            if not self.file_path or not os.path.exists(self.file_path):
                raise FileNotFoundError(f"File not found: {self.file_path}")

            ext = os.path.splitext(self.file_path)[1].lower()

            if ext == ".csv":
                df = csvParser(self.file_path)
            elif ext == ".pdf":
                df = pdfParser(self.file_path)
            else:
                raise ValueError("Unsupported file type. Please select CSV or PDF.")

            if not isinstance(df, pd.DataFrame):
                raise TypeError("Parser did not return a pandas DataFrame.")

            self.progress.emit(100)
            self.finished.emit(df)

        except Exception:
            err = traceback.format_exc()
            logging.error(err)
            self.error.emit(err)


# ================= OVERLAY =================

class Overlay(QWidget):
    def __init__(self, controller):
        super().__init__()

        self.controller = controller

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(50, 50, 460, 280)

        self.label = QLabel()
        self.label.setStyleSheet("""
            color: white;
            font-size: 14px;
            background: rgba(0,0,0,180);
            padding: 10px;
            border-radius: 8px;
        """)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(200)

    @safe_call("Overlay Refresh Error")
    def refresh(self):
        df = self.controller.df
        row = self.controller.row

        if df is None or row >= len(df):
            self.label.setText("DONE")
            return

        r = df.iloc[row]

        self.label.setText(
            f"ROW {row + 1}/{len(df)}\n"
            f"NDC: {r.get('NDC', '')}\n"
            f"QTY: {r.get('QTY', '')}\n"
            f"PRICE: {r.get('PRICE', '')}\n"
            f"TOTAL: {r.get('TOTAL_PRICE', '')}\n"
            f"DATE: {self.controller.date_value}\n"
            f"STATE: {self.controller.state}\n"
            f"PgUp=NDC | PgDn/End=SEQ | Home/F2=NEXT | Del=PREV"
        )

    def closeEvent(self, event):
        try:
            if self.controller:
                self.controller.unregister()
        except Exception:
            notify_error("Overlay Close Error", traceback.format_exc())

        super().closeEvent(event)


# ================= CONTROLLER =================

class GlobalController:
    def __init__(self, df, date_value):
        if not isinstance(df, pd.DataFrame):
            raise TypeError("Overlay requires a pandas DataFrame.")

        self.df = df.reset_index(drop=True).astype(str)
        self.row = 0
        self.state = "READY"
        self.date_value = date_value

        self.total_price = ""
        self.busy = False
        self.hotkeys = []

        self.register()

    def _safe_hotkey(self, func):
        def callback():
            try:
                func()
            except Exception:
                notify_error("Hotkey Error", traceback.format_exc())

        return callback

    def register(self):
        try:
            self.hotkeys.append(keyboard.add_hotkey("page up", self._safe_hotkey(self.send_ndc)))

            # Both Page Down and End will send the sequence.
            self.hotkeys.append(keyboard.add_hotkey("page down", self._safe_hotkey(self.send_sequence)))
            self.hotkeys.append(keyboard.add_hotkey("end", self._safe_hotkey(self.send_sequence)))

            self.hotkeys.append(keyboard.add_hotkey("home", self._safe_hotkey(self.next_row)))
            self.hotkeys.append(keyboard.add_hotkey("f2", self._safe_hotkey(self.next_row)))
            self.hotkeys.append(keyboard.add_hotkey("delete", self._safe_hotkey(self.prev_row)))

        except Exception:
            notify_error(
                "Hotkey Registration Error",
                traceback.format_exc() +
                "\n\nIf you are on Linux, you may need to run with proper keyboard permissions."
            )

    def unregister(self):
        for hotkey in list(self.hotkeys):
            try:
                keyboard.remove_hotkey(hotkey)
            except Exception:
                pass

        self.hotkeys.clear()

    def paste(self, value):
        value = "" if value is None else str(value)
        pyperclip.copy(value)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.08)

    def press_enter(self):
        pyautogui.press("enter")
        time.sleep(0.08)

    def current(self):
        if self.df is None:
            return None

        if self.row < 0 or self.row >= len(self.df):
            return None

        return self.df.iloc[self.row]

    def compute_total(self, qty, price):
        try:
            return float(qty) * float(price)
        except Exception:
            return "INVALID"

    def send_ndc(self):
        if self.busy:
            return

        r = self.current()
        if r is None:
            return

        self.state = "NDC"
        self.paste(r.get("NDC", ""))
        self.press_enter()

    def send_sequence(self):
        if self.busy:
            return

        self.busy = True

        try:
            r = self.current()
            if r is None:
                return

            qty = r.get("QTY", "0")
            price = r.get("PRICE", "0")

            self.total_price = self.compute_total(qty, price)

            self.state = "SEQ"

            self.paste(self.date_value)
            self.press_enter()

            self.paste(qty)
            self.press_enter()

            self.paste(price)
            self.press_enter()

        except Exception:
            notify_error("Send Sequence Error", traceback.format_exc())

        finally:
            self.busy = False

    def next_row(self):
        if self.busy:
            return

        if self.df is None or len(self.df) == 0:
            return

        if self.row < len(self.df) - 1:
            self.row += 1

        self.state = "READY"

    def prev_row(self):
        if self.busy:
            return

        if self.df is None or len(self.df) == 0:
            return

        if self.row > 0:
            self.row -= 1

        self.state = "READY"


# ================= MAIN APP =================

class App(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Invoice Parser")
        self.resize(1200, 800)

        self.file_path = None
        self.df = None

        self.thread = None
        self.worker = None

        self.overlay = None
        self.controller = None

        # Used to prevent itemChanged loops while loading/updating table
        self.loading_table = False

        layout = QVBoxLayout()

        self.drop = QLabel("DROP FILE OR CLICK TO UPLOAD")
        self.drop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop.setStyleSheet("border:2px dashed gray; padding:40px; font-size:18px;")
        self.drop.mousePressEvent = self.pick_file
        layout.addWidget(self.drop)

        self.process_btn = QPushButton("PROCESS")
        self.process_btn.setFixedHeight(50)
        self.process_btn.clicked.connect(lambda: self.start_processing())
        layout.addWidget(self.process_btn)

        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText("MM/DD/YYYY")
        self.date_input.setText(datetime.now().strftime("%m/%d/%Y"))
        self.date_input.setFixedHeight(40)
        layout.addWidget(self.date_input)

        self.summary = QLabel("Rows: 0 | Total: 0")
        self.summary.setStyleSheet("font-size:16px; font-weight:bold;")
        layout.addWidget(self.summary)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        self.table = QTableWidget()
        self.table.itemChanged.connect(self.on_table_item_changed)
        layout.addWidget(self.table)

        self.add_line_btn = QPushButton("ADD NEW LINE")
        self.add_line_btn.setFixedHeight(45)
        self.add_line_btn.clicked.connect(lambda: self.add_new_line())
        layout.addWidget(self.add_line_btn)

        self.start_overlay_btn = QPushButton("START OVERLAY")
        self.start_overlay_btn.setFixedHeight(50)
        self.start_overlay_btn.clicked.connect(lambda: self.start_overlay())
        layout.addWidget(self.start_overlay_btn)

        self.setLayout(layout)

    @safe_call("File Picker Error")
    def pick_file(self, event):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select file",
            "",
            "CSV/PDF (*.csv *.pdf)"
        )

        if path:
            self.file_path = path
            self.drop.setText(os.path.basename(path))

    @safe_call("Start Processing Error")
    def start_processing(self):
        if not self.file_path:
            QMessageBox.warning(self, "Error", "No file selected.")
            return

        if self.thread is not None and self.thread.isRunning():
            QMessageBox.warning(self, "Error", "Processing is already running.")
            return

        self.progress.setValue(0)
        self.process_btn.setEnabled(False)

        self.thread = QThread()
        self.worker = ParserWorker(self.file_path)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)

        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self.on_done)
        self.worker.error.connect(self.on_error)

        # Proper thread cleanup.
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)

        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)

        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._thread_finished)

        self.thread.start()

    def _thread_finished(self):
        self.thread = None
        self.worker = None
        self.process_btn.setEnabled(True)

    @safe_call("Processing Finished Error")
    def on_done(self, df):
        if not isinstance(df, pd.DataFrame):
            raise TypeError("Parser returned invalid data.")

        # Make editable safely
        self.df = df.copy().astype(object)

        self.load_table(self.df)
        self.update_summary()
        self.sync_controller_data()
        self.progress.setValue(100)

    def on_error(self, e):
        notify_error("Parser Error", e)
        self.progress.setValue(0)

    @safe_call("Load Table Error")
    def load_table(self, df):
        if not isinstance(df, pd.DataFrame):
            raise TypeError("load_table expected a pandas DataFrame.")

        self.loading_table = True

        try:
            self.table.clear()
            self.table.setRowCount(len(df))
            self.table.setColumnCount(len(df.columns))
            self.table.setHorizontalHeaderLabels([str(c) for c in df.columns])

            for i in range(len(df)):
                for j in range(len(df.columns)):
                    value = df.iloc[i, j]
                    item = QTableWidgetItem("" if pd.isna(value) else str(value))
                    self.table.setItem(i, j, item)

        finally:
            self.loading_table = False

    @safe_call("Table Edit Error")
    def on_table_item_changed(self, item):
        if self.loading_table:
            return

        if self.df is None:
            return

        row = item.row()
        col = item.column()

        if row < 0 or col < 0:
            return

        if row >= len(self.df):
            return

        if col >= len(self.df.columns):
            return

        column_name = self.df.columns[col]
        new_value = item.text()

        # Update real DataFrame
        self.df.at[row, column_name] = new_value

        # If QTY or PRICE changed, recalculate TOTAL_PRICE automatically
        self.recalculate_total_for_row(row, changed_column=column_name)

        self.update_summary()
        self.sync_controller_data()

    @safe_call("Add New Line Error")
    def add_new_line(self):
        # If no file was processed yet, create a default invoice table
        if self.df is None:
            self.df = pd.DataFrame(
                columns=["NDC", "QTY", "PRICE", "TOTAL_PRICE"],
                dtype=object
            )
            self.load_table(self.df)

        if len(self.df.columns) == 0:
            QMessageBox.warning(self, "Error", "Table has no columns.")
            return

        new_row_index = len(self.df)

        # Add empty row to real DataFrame
        self.df.loc[new_row_index] = {col: "" for col in self.df.columns}

        # Add empty row to visible table
        self.loading_table = True

        try:
            self.table.insertRow(new_row_index)

            for col in range(len(self.df.columns)):
                self.table.setItem(new_row_index, col, QTableWidgetItem(""))

        finally:
            self.loading_table = False

        self.update_summary()
        self.sync_controller_data()

        # Scroll to the new row
        self.table.scrollToBottom()
        self.table.setCurrentCell(new_row_index, 0)

    def _to_float_safe(self, value):
        try:
            value = str(value).strip()
            value = value.replace("$", "").replace(",", "")
            if value == "":
                return None
            return float(value)
        except Exception:
            return None

    @safe_call("Recalculate Total Error")
    def recalculate_total_for_row(self, row, changed_column=None):
        if self.df is None:
            return

        required_cols = ["QTY", "PRICE", "TOTAL_PRICE"]

        for col in required_cols:
            if col not in self.df.columns:
                return

        # Only auto-calculate when QTY or PRICE changes
        if changed_column not in ["QTY", "PRICE"]:
            return

        qty = self._to_float_safe(self.df.at[row, "QTY"])
        price = self._to_float_safe(self.df.at[row, "PRICE"])

        if qty is None or price is None:
            total = ""
        else:
            total = f"{qty * price:.2f}"

        self.df.at[row, "TOTAL_PRICE"] = total

        total_col_index = list(self.df.columns).index("TOTAL_PRICE")

        self.loading_table = True

        try:
            existing_item = self.table.item(row, total_col_index)

            if existing_item is None:
                self.table.setItem(row, total_col_index, QTableWidgetItem(total))
            else:
                existing_item.setText(total)

        finally:
            self.loading_table = False

    @safe_call("Sync Overlay Data Error")
    def sync_controller_data(self):
        """
        Keeps overlay/controller data updated when user edits table.
        Without this, overlay keeps old copied data.
        """
        if self.controller is None:
            return

        if self.df is None:
            self.controller.df = None
            self.controller.row = 0
            return

        current_row = self.controller.row

        self.controller.df = self.df.reset_index(drop=True).astype(str)

        if len(self.controller.df) == 0:
            self.controller.row = 0
        else:
            self.controller.row = max(0, min(current_row, len(self.controller.df) - 1))

    @safe_call("Summary Error")
    def update_summary(self):
        if self.df is None:
            self.summary.setText("Rows: 0 | Total: 0")
            return

        total_rows = len(self.df)

        if "TOTAL_PRICE" in self.df.columns:
            total_sum = pd.to_numeric(
                self.df["TOTAL_PRICE"],
                errors="coerce"
            ).fillna(0).sum()
        else:
            total_sum = 0

        self.summary.setText(f"Rows: {total_rows} | Total: {total_sum:.2f}")

    @safe_call("Start Overlay Error")
    def start_overlay(self):
        if self.df is None:
            QMessageBox.warning(self, "Error", "No data. Process a file first.")
            return

        # Prevent duplicate global hotkeys.
        try:
            if self.overlay is not None:
                self.overlay.close()
                self.overlay = None

            if self.controller is not None:
                self.controller.unregister()
                self.controller = None
        except Exception:
            notify_error("Overlay Cleanup Error", traceback.format_exc())

        self.controller = GlobalController(self.df, self.date_input.text())
        self.overlay = Overlay(self.controller)
        self.overlay.show()

    def closeEvent(self, event):
        try:
            if self.controller is not None:
                self.controller.unregister()

            if self.thread is not None and self.thread.isRunning():
                self.thread.quit()
                self.thread.wait(3000)

        except Exception:
            notify_error("Close Error", traceback.format_exc())

        super().closeEvent(event)


# ================= ENTRY POINT =================

if __name__ == "__main__":
    app = QApplication(sys.argv)

    ERROR_NOTIFIER = ErrorNotifier()

    try:
        w = App()
        w.show()
    except Exception:
        notify_error("Startup Error", traceback.format_exc())

    # Do not wrap this with sys.exit().
    # If an exception is handled, the app remains alive.
    app.exec()
