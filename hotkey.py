import keyboard
import pyperclip
import pyautogui


class GlobalController:
    def __init__(self, df):

        self.df = df.reset_index(drop=True)
        self.row = 0

        # register global hotkeys
        keyboard.add_hotkey("page up", self.send_ndc)
        keyboard.add_hotkey("end", self.send_qty)
        keyboard.add_hotkey("-", self.send_price)
        keyboard.add_hotkey("=", self.next_row)

        print("Hotkeys active:")
        print("PgUp = NDC")
        print("End = QTY")
        print("- = PRICE")
        print("= = NEXT ROW")

    # ---------------- HELPERS ----------------
    def current(self):
        if self.row >= len(self.df):
            return None
        return self.df.iloc[self.row]

    def send_clipboard_and_paste(self, value):
        if value is None:
            return

        pyperclip.copy(str(value))
        pyautogui.hotkey("ctrl", "v")

    # ---------------- ACTIONS ----------------
    def send_ndc(self):
        row = self.current()
        if row is None:
            return

        self.send_clipboard_and_paste(row.get("NDC", ""))

    def send_qty(self):
        row = self.current()
        if row is None:
            return

        self.send_clipboard_and_paste(row.get("INVOICE QTY", ""))

    def send_price(self):
        row = self.current()
        if row is None:
            return

        self.send_clipboard_and_paste(row.get("UNIT PRICE", ""))

    def next_row(self):
        self.row += 1
        print(f"Moved to row {self.row}")