import sys
import os
import logging
import traceback

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
    QHBoxLayout,
    QProgressBar,
    QInputDialog,
    QMenu,
    QAbstractItemView,
)

from parser import parsing


# ================= LOGGING =================

def setup_logging():
    log_dir = os.path.join(os.getenv("LOCALAPPDATA", "."), "InvoiceOCR")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "app.log")

    logging.basicConfig(
        filename=log_file,
        level=logging.ERROR,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    return log_file


LOG_FILE = setup_logging()


def global_exception_hook(exc_type, exc_value, exc_traceback):
    error_text = "".join(
        traceback.format_exception(exc_type, exc_value, exc_traceback)
    )
    logging.error(error_text)

    try:
        QMessageBox.critical(
            None,
            "Unexpected Error",
            f"Unexpected error occurred.\n\nLog saved to:\n{LOG_FILE}",
        )
    except Exception:
        pass


sys.excepthook = global_exception_hook


# ================= OCR WORKER =================

class OCRWorker(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            self.progress.emit(10)
            df = parsing(self.file_path, progress_callback=self.progress.emit)
            self.progress.emit(100)
            self.finished.emit(df)

        except Exception:
            err = traceback.format_exc()
            logging.error(err)
            self.error.emit(err)


# ================= OVERLAY =================

class Overlay(QWidget):
    def __init__(self, controller=None):
        super().__init__()

        self.controller = controller

        self.setWindowTitle("Overlay")

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setGeometry(10, 10, 500, 230)

        self.label = QLabel()
        self.label.setStyleSheet(
            """
            color: white;
            font-size: 15px;
            background: rgba(0,0,0,180);
            padding: 10px;
            border-radius: 8px;
            """
        )

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(200)

    def refresh(self):
        try:
            if self.controller is None or self.controller.df is None:
                self.label.setText("NO DATA")
                return

            df = self.controller.df
            row = self.controller.row
            state = self.controller.state

            if row >= len(df):
                self.label.setText("DONE ✔")
                return

            r = df.iloc[row]

            self.label.setText(
                f"ROW: {row + 1} / {len(df)}\n"
                f"NDC: {r.get('NDC', '')}\n"
                f"QTY: {r.get('INVOICE QTY', '')}\n"
                f"PRICE: {r.get('UNIT PRICE', '')}\n"
                f"STATE: {state}\n"
                f"PgUp=NDC | End=QTY | -=PRICE | ==NEXT"
            )

        except Exception as e:
            logging.error(traceback.format_exc())
            self.label.setText(f"OVERLAY ERROR: {e}")


# ================= GLOBAL CONTROLLER =================

class GlobalController:
    def __init__(self, df, overlay):
        self.df = df.reset_index(drop=True).astype(str)
        self.overlay = overlay

        self.row = 0
        self.state = "READY"
        self.hotkey_handles = []

        self.register_hotkeys()

    def register_hotkeys(self):
        try:
            self.hotkey_handles.append(
                keyboard.add_hotkey("page up", self.safe_call(self.send_ndc))
            )
            self.hotkey_handles.append(
                keyboard.add_hotkey("end", self.safe_call(self.send_qty))
            )
            self.hotkey_handles.append(
                keyboard.add_hotkey("-", self.safe_call(self.send_price))
            )
            self.hotkey_handles.append(
                keyboard.add_hotkey("=", self.safe_call(self.next_row))
            )

        except Exception:
            logging.error(traceback.format_exc())
            self.state = "HOTKEY ERROR"

    def unregister_hotkeys(self):
        for handle in self.hotkey_handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception:
                pass

        self.hotkey_handles.clear()

    def safe_call(self, func):
        def wrapper():
            try:
                func()
            except Exception:
                logging.error(traceback.format_exc())
                self.state = "HOTKEY ERROR"

        return wrapper

    def current(self):
        if self.df is None:
            self.state = "NO DATA"
            return None

        if self.row >= len(self.df):
            self.state = "DONE"
            return None

        return self.df.iloc[self.row]

    def paste(self, value):
        try:
            pyperclip.copy(str(value))
            pyautogui.hotkey("ctrl", "v")

        except Exception:
            logging.error(traceback.format_exc())
            self.state = "PASTE ERROR"

    def send_ndc(self):
        r = self.current()
        if r is None:
            return

        self.state = "PASTE NDC"
        self.paste(r.get("NDC", ""))
        self.state = "WAIT QTY"

    def send_qty(self):
        r = self.current()
        if r is None:
            return

        self.state = "PASTE QTY"
        self.paste(r.get("INVOICE QTY", ""))
        self.state = "WAIT PRICE"

    def send_price(self):
        r = self.current()
        if r is None:
            return

        self.state = "PASTE PRICE"
        self.paste(r.get("UNIT PRICE", ""))
        self.state = "READY NEXT"

    def next_row(self):
        if self.df is None:
            self.state = "NO DATA"
            return

        if self.row < len(self.df):
            self.row += 1

        if self.row >= len(self.df):
            self.state = "DONE"
        else:
            self.state = "READY"


# ================= MAIN APP =================

class App(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("OCR + Overlay + Sync DataFrame")
        self.resize(1200, 800)

        self.file_path = None
        self.df = None
        self.updating = False

        self.thread = None
        self.worker = None

        self.overlay = None
        self.controller = None

        layout = QVBoxLayout()

        self.label = QLabel("Select image")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        # ---------- TOP BUTTONS ----------

        btn_layout = QHBoxLayout()

        self.browse_btn = QPushButton("Browse")
        self.ocr_btn = QPushButton("Start OCR")
        self.overlay_btn = QPushButton("Start Overlay")

        self.browse_btn.clicked.connect(self.browse)
        self.ocr_btn.clicked.connect(self.start_ocr)
        self.overlay_btn.clicked.connect(self.start_overlay)

        btn_layout.addWidget(self.browse_btn)
        btn_layout.addWidget(self.ocr_btn)
        btn_layout.addWidget(self.overlay_btn)

        layout.addLayout(btn_layout)

        # ---------- PROGRESS ----------

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # ---------- TABLE ----------

        self.table = QTableWidget()

        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )

        self.table.cellChanged.connect(self.sync_to_dataframe)

        self.table.horizontalHeader().sectionDoubleClicked.connect(
            self.rename_column_by_index
        )

        self.table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.table.customContextMenuRequested.connect(
            self.show_table_context_menu
        )

        self.table.verticalHeader().setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.table.verticalHeader().customContextMenuRequested.connect(
            self.show_row_header_context_menu
        )

        self.table.horizontalHeader().setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.table.horizontalHeader().customContextMenuRequested.connect(
            self.show_column_header_context_menu
        )

        layout.addWidget(self.table)

        # ---------- BOTTOM ADD ROW BUTTON ----------

        bottom_layout = QHBoxLayout()

        self.add_row_btn = QPushButton("+ Add Row")
        self.add_row_btn.clicked.connect(self.add_row_to_bottom)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.add_row_btn)

        layout.addLayout(bottom_layout)

        self.setLayout(layout)

    # ================= FILE =================

    def browse(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Images (*.jpg *.jpeg *.png *.bmp *.tif *.tiff)",
        )

        if file_path:
            self.file_path = file_path
            self.label.setText(file_path)

    # ================= OCR =================

    def start_ocr(self):
        if not self.file_path:
            QMessageBox.warning(self, "Error", "No file selected")
            return

        if self.thread is not None and self.thread.isRunning():
            QMessageBox.information(self, "OCR", "OCR is already running")
            return

        self.progress.setValue(0)
        self.ocr_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)

        self.thread = QThread()
        self.worker = OCRWorker(self.file_path)

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self.done)
        self.worker.error.connect(self.error)

        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)

        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.ocr_finished_cleanup)

        self.thread.start()

    def ocr_finished_cleanup(self):
        self.ocr_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.thread = None
        self.worker = None

    def done(self, df):
        if df is None:
            QMessageBox.warning(self, "OCR", "OCR returned no data")
            return

        self.df = df.reset_index(drop=True)
        self.load_table(self.df)

        QMessageBox.information(
            self,
            "OCR Complete",
            f"Loaded {len(self.df)} rows",
        )

    def error(self, msg):
        QMessageBox.critical(
            self,
            "OCR Error",
            f"OCR failed.\n\nLog saved to:\n{LOG_FILE}\n\n{msg[:3000]}",
        )

    # ================= TABLE LOAD =================

    def load_table(self, df):
        self.updating = True

        try:
            self.table.clear()
            self.table.setRowCount(len(df))
            self.table.setColumnCount(len(df.columns))

            self.table.setHorizontalHeaderLabels(
                [str(c) for c in df.columns]
            )

            for i in range(len(df)):
                self.table.setVerticalHeaderItem(
                    i,
                    QTableWidgetItem(str(i + 1))
                )

                for j in range(len(df.columns)):
                    value = "" if pd.isna(df.iloc[i, j]) else str(df.iloc[i, j])
                    self.table.setItem(i, j, QTableWidgetItem(value))

            self.table.resizeColumnsToContents()

        finally:
            self.updating = False

    # ================= SYNC TABLE TO DATAFRAME =================

    def sync_to_dataframe(self, row, col):
        if self.df is None or self.updating:
            return

        try:
            if row >= len(self.df) or col >= len(self.df.columns):
                return

            item = self.table.item(row, col)

            if item is None:
                return

            value = item.text()
            self.df.iat[row, col] = value

            self.refresh_controller_df()

        except Exception:
            logging.error(traceback.format_exc())

    def refresh_controller_df(self):
        try:
            if self.controller is not None and self.df is not None:
                self.controller.df = self.df.reset_index(drop=True).astype(str)

                if len(self.controller.df) == 0:
                    self.controller.row = 0
                    self.controller.state = "NO DATA"

                elif self.controller.row >= len(self.controller.df):
                    self.controller.row = len(self.controller.df) - 1
                    self.controller.state = "READY"

        except Exception:
            logging.error(traceback.format_exc())

    # ================= ADD ROW =================

    def add_row_to_bottom(self):
        if self.df is None:
            QMessageBox.warning(self, "Error", "Run OCR first")
            return

        try:
            self.updating = True

            new_row = {col: "" for col in self.df.columns}
            self.df.loc[len(self.df)] = new_row
            self.df = self.df.reset_index(drop=True)

            new_row_index = self.table.rowCount()
            self.table.insertRow(new_row_index)

            self.table.setVerticalHeaderItem(
                new_row_index,
                QTableWidgetItem(str(new_row_index + 1))
            )

            for col in range(self.table.columnCount()):
                self.table.setItem(
                    new_row_index,
                    col,
                    QTableWidgetItem("")
                )

            self.table.scrollToBottom()
            self.table.selectRow(new_row_index)

            self.refresh_controller_df()

        except Exception:
            logging.error(traceback.format_exc())
            QMessageBox.critical(self, "Error", "Could not add row")

        finally:
            self.updating = False

    # ================= RENAME COLUMN =================

    def rename_column_by_index(self, col):
        if self.df is None:
            QMessageBox.warning(self, "Error", "No data loaded")
            return

        if col < 0 or col >= len(self.df.columns):
            return

        old_name = str(self.df.columns[col])

        new_name, ok = QInputDialog.getText(
            self,
            "Rename Column",
            f"Rename column '{old_name}' to:",
            text=old_name,
        )

        if not ok:
            return

        new_name = new_name.strip()

        if not new_name:
            QMessageBox.warning(self, "Error", "Column name cannot be empty")
            return

        if new_name in self.df.columns and new_name != old_name:
            QMessageBox.warning(self, "Error", "Column name already exists")
            return

        try:
            self.updating = True

            columns = list(self.df.columns)
            columns[col] = new_name
            self.df.columns = columns

            self.table.setHorizontalHeaderItem(
                col,
                QTableWidgetItem(new_name)
            )

            self.refresh_controller_df()

        except Exception:
            logging.error(traceback.format_exc())
            QMessageBox.critical(self, "Error", "Could not rename column")

        finally:
            self.updating = False

    # ================= RIGHT CLICK TABLE BODY =================

    def show_table_context_menu(self, pos):
        if self.df is None:
            return

        selected_rows = sorted(
            set(index.row() for index in self.table.selectedIndexes())
        )

        if not selected_rows:
            row = self.table.rowAt(pos.y())

            if row >= 0:
                selected_rows = [row]
                self.table.selectRow(row)

        if not selected_rows:
            return

        menu = QMenu(self)

        delete_action = menu.addAction(
            f"Delete Selected Row(s) ({len(selected_rows)})"
        )

        action = menu.exec(self.table.viewport().mapToGlobal(pos))

        if action == delete_action:
            self.delete_rows(selected_rows)

    # ================= RIGHT CLICK ROW HEADER =================

    def show_row_header_context_menu(self, pos):
        if self.df is None:
            return

        row = self.table.verticalHeader().logicalIndexAt(pos)

        selected_rows = sorted(
            set(index.row() for index in self.table.selectedIndexes())
        )

        if row >= 0 and row not in selected_rows:
            selected_rows = [row]
            self.table.selectRow(row)

        if not selected_rows:
            return

        menu = QMenu(self)

        delete_action = menu.addAction(
            f"Delete Row(s) ({len(selected_rows)})"
        )

        action = menu.exec(
            self.table.verticalHeader().viewport().mapToGlobal(pos)
        )

        if action == delete_action:
            self.delete_rows(selected_rows)

    # ================= RIGHT CLICK COLUMN HEADER =================

    def show_column_header_context_menu(self, pos):
        if self.df is None:
            return

        col = self.table.horizontalHeader().logicalIndexAt(pos)

        selected_cols = sorted(
            set(index.column() for index in self.table.selectedIndexes())
        )

        if col >= 0 and col not in selected_cols:
            selected_cols = [col]
            self.table.selectColumn(col)

        if not selected_cols:
            return

        menu = QMenu(self)

        rename_action = None

        if len(selected_cols) == 1:
            rename_action = menu.addAction("Rename Column")

        delete_action = menu.addAction(
            f"Delete Column(s) ({len(selected_cols)})"
        )

        action = menu.exec(
            self.table.horizontalHeader().viewport().mapToGlobal(pos)
        )

        if rename_action is not None and action == rename_action:
            self.rename_column_by_index(selected_cols[0])

        elif action == delete_action:
            self.delete_columns(selected_cols)

    # ================= DELETE ROWS =================

    def delete_rows(self, rows):
        if self.df is None:
            return

        rows = sorted(
            set(r for r in rows if 0 <= r < self.table.rowCount())
        )

        if not rows:
            return

        confirm = QMessageBox.question(
            self,
            "Delete Rows",
            f"Delete {len(rows)} selected row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            self.updating = True

            for row in sorted(rows, reverse=True):
                self.table.removeRow(row)

            self.df = self.df.drop(index=rows).reset_index(drop=True)

            self.refresh_row_labels()
            self.refresh_controller_df()

        except Exception:
            logging.error(traceback.format_exc())
            QMessageBox.critical(self, "Error", "Could not delete row(s)")

        finally:
            self.updating = False

    # ================= DELETE COLUMNS =================

    def delete_columns(self, cols):
        if self.df is None:
            return

        cols = sorted(
            set(c for c in cols if 0 <= c < self.table.columnCount())
        )

        if not cols:
            return

        col_names = [
            str(self.df.columns[c])
            for c in cols
            if 0 <= c < len(self.df.columns)
        ]

        protected_cols = ["NDC", "INVOICE QTY", "UNIT PRICE"]
        deleting_protected = [c for c in col_names if c in protected_cols]

        if deleting_protected:
            message = (
                "You are deleting important overlay column(s):\n\n"
                + "\n".join(deleting_protected)
                + "\n\nOverlay paste may stop working.\n\nContinue?"
            )
        else:
            message = f"Delete {len(cols)} selected column(s)?"

        confirm = QMessageBox.question(
            self,
            "Delete Columns",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            self.updating = True

            for col in sorted(cols, reverse=True):
                self.table.removeColumn(col)

            self.df = self.df.drop(columns=col_names)

            self.refresh_controller_df()

        except Exception:
            logging.error(traceback.format_exc())
            QMessageBox.critical(self, "Error", "Could not delete column(s)")

        finally:
            self.updating = False

    # ================= ROW LABELS =================

    def refresh_row_labels(self):
        for row in range(self.table.rowCount()):
            self.table.setVerticalHeaderItem(
                row,
                QTableWidgetItem(str(row + 1))
            )

    # ================= OVERLAY =================

    def start_overlay(self):
        if self.df is None:
            QMessageBox.warning(self, "Error", "Run OCR first")
            return

        try:
            if self.controller is not None:
                self.controller.unregister_hotkeys()
                self.controller = None

            if self.overlay is not None:
                self.overlay.close()
                self.overlay = None

            self.overlay = Overlay(None)
            self.controller = GlobalController(self.df, self.overlay)
            self.overlay.controller = self.controller

            self.overlay.show()

            QMessageBox.information(
                self,
                "Active",
                "PgUp=NDC | End=QTY | -=PRICE | ==NEXT ROW",
            )

        except Exception:
            logging.error(traceback.format_exc())
            QMessageBox.critical(
                self,
                "Overlay Error",
                f"Could not start overlay.\n\nLog saved to:\n{LOG_FILE}",
            )

    # ================= CLOSE =================

    def closeEvent(self, event):
        try:
            if self.controller is not None:
                self.controller.unregister_hotkeys()
        except Exception:
            pass

        try:
            if self.overlay is not None:
                self.overlay.close()
        except Exception:
            pass

        event.accept()


# ================= RUN =================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = App()
    w.show()
    sys.exit(app.exec())