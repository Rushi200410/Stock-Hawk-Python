import json
import threading
import websocket as ws_module
from datetime import datetime, timedelta
from tkinter import Button, Canvas, Frame, Label, Toplevel, Tk
from tkinter import ttk

import config
from kiteconnect import KiteConnect


class KiteDashboardApp:
    def __init__(self):
        self.kite = None
        self.access_token = ''
        self.ws_app = None
        self.root = Tk()
        self.root.geometry('750x350')
        self.root.title('Kite OI Dashboard')
        self.root.config(background='black')
        self._build_ui()

    def _build_ui(self):
        self.style = ttk.Style()
        self.style.theme_use('winnative')
        self.top_frame = Frame(self.root, background='black')

        self.connect_button = Button(
            self.top_frame,
            text='NOT CONNECTED',
            command=self._open_token_popup,
            width=13,
            bg='red',
            fg='black',
            font=('Arial Black', 10),
        )
        self.connect_button.grid(row=0, column=0, padx=4, pady=4)

        self.index_select = ttk.Combobox(
            self.top_frame,
            values=['NIFTY', 'BANKNIFTY'],
            width=13,
            font=('Arial Bold', 10),
        )
        self.index_select.current(0)
        self.index_select.grid(row=0, column=1, padx=4)

        self.expiries = ttk.Combobox(
            self.top_frame,
            values=[],
            width=13,
            font=('Arial Bold', 10),
        )
        self.expiries.grid(row=0, column=2, padx=4)

        self.time_frame = ttk.Combobox(
            self.top_frame,
            values=['5minute', '10minute', '15minute', '30minute', '60minute', 'day'],
            width=13,
            font=('Arial Bold', 10),
        )
        self.time_frame.current(0)
        self.time_frame.grid(row=0, column=3, padx=4)

        Button(
            self.top_frame,
            text='OPTION CHAIN',
            command=self._start_option_chain_thread,
            width=13,
            bg='palegreen',
            fg='black',
            font=('Arial Black', 10),
        ).grid(row=0, column=4, padx=4)

        self.top_frame.pack(fill='x', padx=10, pady=10)

    def _start_option_chain_thread(self):
        thread = threading.Thread(target=self._render_option_chain, daemon=True)
        thread.start()

    def _open_token_popup(self):
        self.token_popup = Toplevel(self.root)
        self.token_popup.title('Enter Request Token')
        self.token_popup.geometry('420x90')
        entry_token = ttk.Entry(self.token_popup, width=50)
        entry_token.grid(row=0, column=0, padx=8, pady=8)
        Button(
            self.token_popup,
            text='SUBMIT',
            command=lambda: self._connect_zerodha(entry_token.get()),
            width=10,
            bg='palegreen',
            fg='black',
        ).grid(row=0, column=1, padx=8)

    def _connect_zerodha(self, request_token: str):
        request_token = request_token.strip()
        if not request_token:
            return
        try:
            self.kite = KiteConnect(api_key=config.API_KEY)
            data = self.kite.generate_session(request_token, api_secret=config.API_SECRET)
            self.access_token = data['access_token']
            self.kite.set_access_token(self.access_token)
            self.connect_button.config(bg='palegreen', text='CONNECTED')
            if hasattr(self, 'token_popup'):
                self.token_popup.destroy()
            self._refresh_expiry_list()
            self._connect_websocket()
        except Exception as e:
            print('Error connecting to Zerodha:', e)

    def _connect_websocket(self):
        if not self.access_token:
            return
        self.websocket_url = f'wss://websocket.kite.trade?api_key={config.API_KEY}&access_token={self.access_token}'
        try:
            self.ws_app = ws_module.WebSocketApp(
                self.websocket_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
            )
            thread = threading.Thread(target=self.ws_app.run_forever, daemon=True)
            thread.start()
        except Exception as e:
            print('Error connecting to WebSocket:', e)

    def _on_open(self, ws):
        print('WebSocket connection established.')

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            print('Received data:', data)
        except json.JSONDecodeError as e:
            print('Error decoding JSON data:', e)

    def _on_error(self, ws, error):
        print('Error receiving data from WebSocket:', error)

    def _refresh_expiry_list(self):
        if not self.kite:
            return
        symbol = self.index_select.get()
        self.expiries['values'] = self._find_possible_expiries(symbol)

    def _find_possible_expiries(self, symbol: str):
        if not self.kite:
            return []
        values = []
        today = datetime.today()
        for offset in range(0, 30):
            expiry_date = today + timedelta(days=offset)
            year = expiry_date.strftime('%y')
            month = expiry_date.strftime('%b').upper()
            day = expiry_date.strftime('%d')
            if symbol == 'BANKNIFTY':
                strike = f'BANKNIFTY{year}{month}{day}'
            else:
                strike = f'NIFTY{year}{month}{day}'
            values.append(f'{year}-{month}-{day}')
        return list(dict.fromkeys(values))

    def _render_option_chain(self):
        if not self.kite:
            print('API not connected yet.')
            return
        try:
            if hasattr(self, 'chain_frame'):
                self.chain_frame.destroy()
        except Exception:
            pass
        self.chain_frame = Frame(self.root)
        canvas = Canvas(self.chain_frame)
        scrollbar = ttk.Scrollbar(self.chain_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all')),
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(width=700, height=700, yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        self.chain_frame.pack(fill='both', expand=True, padx=10, pady=10)

        symbol = self.index_select.get()
        quote_symbol = 'NSE:NIFTY BANK' if symbol == 'BANKNIFTY' else 'NSE:NIFTY_50'
        quote = self.kite.quote(quote_symbol)
        price = int(quote[quote_symbol]['last_price'])
        incrementor = 100 if symbol == 'BANKNIFTY' else 50
        price = price - price % incrementor
        strike_count = 20

        headers = ['CE_OI', 'LTP', 'CHANGE', 'STRIKE', 'LTP', 'CHANGE', 'PE_OI']
        for col, text in enumerate(headers):
            Label(
                scrollable_frame,
                text=text,
                width=10,
                bg='gray',
                font=('Arial Black', 10),
            ).grid(row=0, column=col, padx=1, pady=1)

        current_price = price - int(strike_count / 2) * incrementor
        instruments = []
        for row in range(1, strike_count + 1):
            expiry_value = self.expiries.get() or ''
            expiry_symbol = expiry_value.replace('-', '')
            strike_code = f'{symbol}{expiry_symbol}{current_price}'
            instruments.append(f'NFO:{strike_code}CE')
            instruments.append(f'NFO:{strike_code}PE')
            Label(scrollable_frame, text='', width=10, font=('Arial bold', 10)).grid(row=row, column=0)
            Label(scrollable_frame, text='', width=10, font=('Arial bold', 10)).grid(row=row, column=1)
            Label(scrollable_frame, text='', width=10, font=('Arial bold', 10)).grid(row=row, column=2)
            label = Label(
                scrollable_frame,
                text=current_price,
                width=10,
                bg='burlywood2',
                font=('Arial bold', 10),
            )
            label.grid(row=row, column=3)
            Label(scrollable_frame, text='', width=10, font=('Arial bold', 10)).grid(row=row, column=4)
            Label(scrollable_frame, text='', width=10, font=('Arial bold', 10)).grid(row=row, column=5)
            Label(scrollable_frame, text='', width=10, font=('Arial bold', 10)).grid(row=row, column=6)
            if row == strike_count // 2:
                label.config(bg='springgreen')
            current_price += incrementor

        batch_quote = self.kite.quote(instruments)
        widgets = scrollable_frame.winfo_children()
        for row in range(1, strike_count + 1):
            ce_index = (row * 7) + 1
            pe_index = (row * 7) + 4
            ce_symbol = instruments[(row - 1) * 2]
            pe_symbol = instruments[(row - 1) * 2 + 1]
            try:
                widgets[ce_index]['text'] = batch_quote[ce_symbol]['last_price']
            except Exception:
                widgets[ce_index]['text'] = 'N/A'
            try:
                widgets[pe_index]['text'] = batch_quote[pe_symbol]['last_price']
            except Exception:
                widgets[pe_index]['text'] = 'N/A'

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = KiteDashboardApp()
    app.run()
