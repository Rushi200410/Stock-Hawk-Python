import sys
import os
import csv
import json
import time
import threading
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QSpinBox, QComboBox, QPushButton,
                             QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
                             QLineEdit, QInputDialog, QMessageBox)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont
from kiteconnect import KiteConnect
from kite_auth import KiteAuthenticator

import hawk_engine
import config
import mock_generator
from snapshot import cleanup_old_files

class StockHawkDesktop(QMainWindow):
    market_data_ready = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🦅 StockHawk Desktop Terminal")
        self.resize(1000, 750)
        
        self.kite_auth = KiteAuthenticator()
        self.kite_instance = None
        self.latest_market_data = None
        self.previous_market_data = None
        self.interval_reference_data = None
        self.monitor_display_start_data = None
        self.monitor_display_end_data = None
        self.last_pattern_check_ts = 0.0
        self.last_aux_refresh_ts = 0.0
        self.last_cleanup_ts = 0.0
        
        self.init_ui()
        self.market_data_ready.connect(self._finish_background_refresh)
        
        # Start the background timer to fetch snapshots without freezing UI
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.run_engine_step)
        self.timer.start(max(3000, config.FETCH_INTERVAL * 1000))
        
        self.current_interval_minutes = 0
        self.last_milestone_time = datetime.now()
        
        # Clock Timer (ticks every 1 second)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        
        # Initial data load
        self.run_engine_step()
        self.update_clock()
        
        # Auto-load token on startup if valid
        if self.kite_auth.load_token():
            self.auth_status.setText("Status: Authenticated ✅ (Loaded)")
            self.kite_instance = self.kite_auth.kite

    def update_clock(self):
        """Updates the real-time clock display."""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.clock_label.setText(current_time)

    def run_engine_step(self):
        """Switches the app from MOCK data to REAL Kite data."""
        import kite_engine # Import your new real-data fetcher
        import hawk_engine
        from snapshot import snapshot_manager, cleanup_old_files

        selected_symbol = self.symbol_combo.currentText()
        selected_expiry = self.expiry_combo.currentText()
        kite_inst = getattr(self, "kite_instance", None)

        real_market_data = kite_engine.fetch_real_market_data(
            kite_inst,
            symbol=selected_symbol,
            expiry=selected_expiry,
        )

        if real_market_data:
            snapshot_manager.save(real_market_data)
        else:
            real_market_data = mock_generator.start_simulation_once()

        self.market_data_ready.emit(real_market_data)

        now = time.monotonic()
        if now - self.last_pattern_check_ts >= 15:
            hawk_engine.check_for_patterns()
            self.last_pattern_check_ts = now

        if now - self.last_cleanup_ts >= 300:
            cleanup_old_files()
            self.last_cleanup_ts = now

        if self.current_interval_minutes > 0:
            now_dt = datetime.now()
            diff = (now_dt - self.last_milestone_time).total_seconds() / 60

            if diff >= self.current_interval_minutes:
                # 1. Freeze the data for the UI to display statically over the next interval
                self.monitor_display_start_data = self.interval_reference_data
                self.monitor_display_end_data = self.latest_market_data
                
                # 2. Generate Telegram alert based on this shift
                self.generate_interval_report()
                self.last_milestone_time = now_dt
                # 3. Reset the background reference frame for the NEXT interval calculation
                self.interval_reference_data = self.latest_market_data
                self.render_latest_data()

    def manual_refresh(self):
        """Force an immediate data update without waiting for the 3-second timer."""
        print("🔄 Manual refresh triggered...")
        self.run_engine_step()

    def update_interval_settings(self, text):
        if text == "OFF":
            self.current_interval_minutes = 0
            self.interval_reference_data = None
            self.monitor_display_start_data = None
            self.monitor_display_end_data = None
        else:
            self.current_interval_minutes = int(text.split(" ")[0])
            self.last_milestone_time = datetime.now()
            self.interval_reference_data = self.latest_market_data
            
            # Attempt to instantly populate with historical data if available
            target_dt = datetime.now() - timedelta(minutes=self.current_interval_minutes)
            best_snap_data = None
            snap_folder = config.SNAPSHOT_FOLDER
            if os.path.exists(snap_folder):
                files = [f for f in os.listdir(snap_folder) if f.startswith('snap_') and f.endswith('.json')]
                files.sort(reverse=True) # Newest first
                
                for f in files:
                    try:
                        ts_str = f[5:20]
                        snap_dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                        if snap_dt <= target_dt:
                            # Ensure the snapshot isn't extremely outdated (max 2 minutes extra)
                            if (target_dt - snap_dt) <= timedelta(minutes=2):
                                with open(os.path.join(snap_folder, f), 'r', encoding='utf-8') as sf:
                                    best_snap_data = json.load(sf).get("data")
                            break
                    except Exception:
                        continue
            
            self.monitor_display_start_data = best_snap_data
            self.monitor_display_end_data = self.latest_market_data if best_snap_data else None
            print(f"Milestone interval set to {self.current_interval_minutes} minutes")
            
        self.render_latest_data()

    def generate_interval_report(self):
        """Compares current data with the reference memory snapshot."""
        if not self.latest_market_data or not self.interval_reference_data: 
            return
        
        report_msg = hawk_engine.compare_interval_data(
            self.latest_market_data, self.interval_reference_data, self.current_interval_minutes
        )
        if report_msg:
            from notifier import send_master_alert
            send_master_alert(report_msg, symbol="MARKET", pattern=f"{self.current_interval_minutes}M_UPDATE")

    def init_ui(self):
        # Main Container
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setSpacing(20)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        # Apply Global Stylesheet
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #0f0f0f; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
            QLabel { font-size: 14px; }
            QTableWidget { 
                background-color: #1a1a1a; gridline-color: #333333; 
                border: 1px solid #333333; border-radius: 8px; font-size: 13px;
            }
            QHeaderView::section { 
                background-color: #252525; color: #888888; font-weight: bold; 
                border: 1px solid #333333; padding: 6px;
            }
            QComboBox, QSpinBox { 
                background-color: #333333; color: white; border: 1px solid #555555; 
                padding: 4px; border-radius: 4px;
            }
            QPushButton { 
                background-color: #00ff95; color: black; font-weight: bold; 
                border: none; padding: 6px 15px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #00cc7a; }
            QTabWidget::pane { border: 1px solid #333; background: #1a1a1a; border-radius: 8px; }
            QTabBar::tab { background: #252525; padding: 10px 20px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 5px; }
            QTabBar::tab:selected { background: #00ff95; color: black; font-weight: bold; }
        """)

        # Create the Tab Widget
        self.tabs = QTabWidget()
        
        # --- TAB 1: MARKET DASHBOARD ---
        self.market_tab = QWidget()
        self.setup_market_tab()
        self.tabs.addTab(self.market_tab, "Market")

        # --- TAB 2: SETTINGS (API Integration) ---
        self.settings_tab = QWidget()
        self.setup_settings_tab()
        self.tabs.addTab(self.settings_tab, "Settings")

        self.main_layout.addWidget(self.tabs)

    def setup_market_tab(self):
        layout = QVBoxLayout(self.market_tab)
        layout.setSpacing(20)

        # --- CONTROL BAR ---
        control_layout = QHBoxLayout()
        control_layout.setSpacing(15)
        
        # Status Light
        status_light = QLabel()
        status_light.setFixedSize(14, 14)
        status_light.setStyleSheet("background-color: #00ff95; border-radius: 7px;")
        control_layout.addWidget(status_light)
        
        status_label = QLabel("CONNECTED")
        status_label.setStyleSheet("color: #00ff95; font-weight: bold;")
        control_layout.addWidget(status_label)
        
        control_layout.addSpacing(20)
        
        # Snapshot Control
        control_layout.addWidget(QLabel("Snapshots:"))
        self.snap_spin = QSpinBox()
        self.snap_spin.setRange(1, 100)
        self.snap_spin.setValue(10)
        self.snap_spin.valueChanged.connect(self.run_engine_step) # Instantly update when changed
        control_layout.addWidget(self.snap_spin)
        
        # Interval Selection
        control_layout.addWidget(QLabel("Monitoring:"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["OFF", "1 Min", "5 Min", "15 Min"])
        self.interval_combo.currentTextChanged.connect(self.update_interval_settings)
        control_layout.addWidget(self.interval_combo)
        
        # Strike Count Control
        control_layout.addWidget(QLabel("Strikes:"))
        self.strike_spin = QSpinBox()
        self.strike_spin.setRange(1, 10) # Min 3, Max 10
        self.strike_spin.setValue(1) # Default to your current view
        self.strike_spin.valueChanged.connect(self.run_engine_step)
        control_layout.addWidget(self.strike_spin)
        
        # Symbol Selection
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["NIFTY", "BANKNIFTY", "CRUDEOIL"])
        self.symbol_combo.currentTextChanged.connect(self.run_engine_step) # Instantly update
        self.symbol_combo.currentTextChanged.connect(self.refresh_expiry_list)
        control_layout.addWidget(self.symbol_combo)
        
        # Expiry Selection
        self.expiry_combo = QComboBox()
        self.expiry_combo.currentTextChanged.connect(self.run_engine_step)
        control_layout.addWidget(self.expiry_combo)
        self.refresh_expiry_list() # Populate initially based on default symbol
        
        # Option Chain Button
        btn_chain = QPushButton("OPTION CHAIN")
        control_layout.addWidget(btn_chain)
        
        self.refresh_btn = QPushButton("🔄 REFRESH")
        self.refresh_btn.setStyleSheet("""
            QPushButton { 
                background-color: #00ff95; color: black; font-weight: bold; 
                padding: 5px 15px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #00cc7a; }
        """)
        self.refresh_btn.clicked.connect(self.manual_refresh)
        control_layout.addWidget(self.refresh_btn)
        
        control_layout.addStretch()
        
        # Real-time Clock Label
        self.clock_label = QLabel("00:00:00")
        self.clock_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff; background: #333333; padding: 4px 10px; border-radius: 4px;")
        control_layout.addWidget(self.clock_label)
        
        layout.addLayout(control_layout)

        # --- STATS BAR ---
        stats_layout = QHBoxLayout()
        self.pcr_label = QLabel("PCR: 0.00")
        self.sentiment_label = QLabel("Sentiment: Neutral")
        self.pcr_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #00ff95;")
        self.sentiment_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        
        stats_layout.addWidget(self.pcr_label)
        stats_layout.addSpacing(40)
        stats_layout.addWidget(self.sentiment_label)
        stats_layout.addStretch()
        
        layout.addLayout(stats_layout)

        # --- SUB TABS (Live Chain vs Interval Monitor) ---
        self.sub_tabs = QTabWidget()
        
        # 1. LIVE CHAIN SUB-TAB
        self.chain_tab = QWidget()
        chain_layout = QVBoxLayout(self.chain_tab)
        
        self.chain_label = QLabel("Options Chain (Live)")
        self.chain_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #00ff95;")
        chain_layout.addWidget(self.chain_label)

        self.chain_table = QTableWidget(0, 7)
        self.chain_table.setHorizontalHeaderLabels([
            "CE OI", "CE Change", "CE LTP", "Strike", "PE LTP", "PE Change", "PE OI"
        ])
        self.chain_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.chain_table.verticalHeader().setVisible(False)
        self.chain_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.chain_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        chain_layout.addWidget(self.chain_table)
        self.sub_tabs.addTab(self.chain_tab, "Live Options Chain")

        # 2. INTERVAL MONITOR SUB-TAB
        self.monitor_tab = QWidget()
        monitor_layout = QVBoxLayout(self.monitor_tab)
        
        self.monitor_label = QLabel("Interval Monitor: Changes Since Last Check")
        self.monitor_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #00ff95;")
        monitor_layout.addWidget(self.monitor_label)

        self.monitor_table = QTableWidget(0, 5)
        self.monitor_table.setHorizontalHeaderLabels([
            "CE OI Δ", "CE LTP Δ", "Strike", "PE LTP Δ", "PE OI Δ"
        ])
        self.monitor_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.monitor_table.verticalHeader().setVisible(False)
        self.monitor_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.monitor_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        monitor_layout.addWidget(self.monitor_table)
        self.sub_tabs.addTab(self.monitor_tab, "Interval Monitor")
        
        layout.addWidget(self.sub_tabs, stretch=3)

        # --- ALERTS SECTION (Bottom of Market Page) ---
        alerts_label = QLabel("Recent Pattern Hits & Alerts")
        alerts_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(alerts_label)
        
        self.alerts_table = QTableWidget(0, 4)
        self.alerts_table.setHorizontalHeaderLabels(["Time", "Symbol", "Pattern", "Message"])
        self.alerts_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.alerts_table.verticalHeader().setVisible(False)
        self.alerts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.alerts_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.alerts_table, stretch=1)

    def refresh_expiry_list(self):
        """Dynamically changes expiry options based on the selected asset."""
        symbol = self.symbol_combo.currentText()
        all_dates = hawk_engine.get_live_expiries()

        self.expiry_combo.blockSignals(True)
        try:
            self.expiry_combo.clear()
            if symbol in all_dates:
                self.expiry_combo.addItems(all_dates[symbol])
        finally:
            self.expiry_combo.blockSignals(False)

    def _get_or_create_item(self, table, row, col):
        """Helper to safely get or create table cells to avoid UI flickering."""
        item = table.item(row, col)
        if not item:
            item = QTableWidgetItem()
            table.setItem(row, col, item)
        return item

    def update_data(self):
        self.render_latest_data()

    def _finish_background_refresh(self, market_data):
        if market_data:
            self.previous_market_data = self.latest_market_data
            self.latest_market_data = market_data

        self.render_latest_data()

    def render_latest_data(self):
        """Updates the live view from the cached market snapshot."""
        if not self.latest_market_data:
            return

        selected_symbol = self.symbol_combo.currentText()
        live_data = self.latest_market_data

        if selected_symbol not in live_data:
            return

        current_chain = live_data[selected_symbol].get("optionsChain", [])
        self.chain_label.setText(f"{selected_symbol} Options Chain (Live) - ₹{live_data[selected_symbol]['price']}")

        metrics = hawk_engine.calculate_market_metrics(current_chain)
        self.pcr_label.setText(f"PCR: {metrics['pcr']}")
        self.sentiment_label.setText(f"Sentiment: {metrics['sentiment']}")

        if self.previous_market_data and selected_symbol in self.previous_market_data:
            old_oi_map = {
                opt["strikePrice"]: {"CE_OI": opt["CE"]["OI"], "PE_OI": opt["PE"]["OI"]}
                for opt in self.previous_market_data[selected_symbol].get("optionsChain", [])
            }
            for opt in current_chain:
                strike = opt["strikePrice"]
                opt["CE"]["changeInOI"] = opt["CE"]["OI"] - old_oi_map.get(strike, {"CE_OI": opt["CE"]["OI"]})["CE_OI"]
                opt["PE"]["changeInOI"] = opt["PE"]["OI"] - old_oi_map.get(strike, {"PE_OI": opt["PE"]["OI"]})["PE_OI"]

        num_strikes = self.strike_spin.value()
        atm_index = -1
        for i, opt in enumerate(current_chain):
            if opt.get("isATM"):
                atm_index = i
                break

        if atm_index != -1:
            start = max(0, atm_index - num_strikes)
            end = min(len(current_chain), atm_index + num_strikes + 1)
            display_chain = current_chain[start:end]
        else:
            display_chain = current_chain

        self.chain_table.setRowCount(len(display_chain))
        for r, opt in enumerate(display_chain):
            bg_color = QColor(0, 255, 149, 38) if opt.get("isATM") else QColor("#1a1a1a")
            ce_change_color = QColor("#00ff95") if opt["CE"]["changeInOI"] > 0 else (QColor("#ff4d4d") if opt["CE"]["changeInOI"] < 0 else QColor("#e0e0e0"))
            pe_change_color = QColor("#00ff95") if opt["PE"]["changeInOI"] > 0 else (QColor("#ff4d4d") if opt["PE"]["changeInOI"] < 0 else QColor("#e0e0e0"))

            cells_data = [
                (str(opt["CE"]["OI"]), QColor("#e0e0e0"), False, Qt.AlignmentFlag.AlignLeft),
                (str(opt["CE"]["changeInOI"]), ce_change_color, False, Qt.AlignmentFlag.AlignLeft),
                (f"₹{opt['CE']['LTP']}", QColor("#e0e0e0"), False, Qt.AlignmentFlag.AlignLeft),
                (str(opt["strikePrice"]), QColor("#ffffff"), True, Qt.AlignmentFlag.AlignCenter),
                (f"₹{opt['PE']['LTP']}", QColor("#e0e0e0"), False, Qt.AlignmentFlag.AlignLeft),
                (str(opt["PE"]["changeInOI"]), pe_change_color, False, Qt.AlignmentFlag.AlignLeft),
                (str(opt["PE"]["OI"]), QColor("#e0e0e0"), False, Qt.AlignmentFlag.AlignLeft),
            ]

            for c, (text, fg_color, bold, align) in enumerate(cells_data):
                item = self._get_or_create_item(self.chain_table, r, c)
                item.setText(text)
                item.setForeground(QBrush(fg_color))
                item.setBackground(QBrush(bg_color))
                item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                font = QFont()
                font.setBold(bold)
                item.setFont(font)

        self.render_monitor_table(selected_symbol)
        self._refresh_auxiliary_tables_if_needed()

    def render_monitor_table(self, selected_symbol):
        """Renders the static differences from the last completed interval."""
        if not self.monitor_display_start_data or not self.monitor_display_end_data or selected_symbol not in self.monitor_display_end_data:
            self.monitor_table.setRowCount(0)
            if self.current_interval_minutes > 0:
                self.monitor_label.setText(f"Interval Monitor: Waiting for first {self.current_interval_minutes}m interval to complete...")
            else:
                self.monitor_label.setText("Interval Monitor: OFF")
            return
            
        self.monitor_label.setText(f"{selected_symbol} Monitor - Difference over last {self.current_interval_minutes}m interval")
        
        end_chain = self.monitor_display_end_data[selected_symbol].get("optionsChain", [])
        ref_chain = self.monitor_display_start_data.get(selected_symbol, {}).get("optionsChain", [])
        
        num_strikes = self.strike_spin.value()
        atm_index = -1
        for i, opt in enumerate(end_chain):
            if opt.get("isATM"):
                atm_index = i
                break

        if atm_index != -1:
            start = max(0, atm_index - num_strikes)
            end = min(len(end_chain), atm_index + num_strikes + 1)
            display_chain = end_chain[start:end]
        else:
            display_chain = end_chain
            
        self.monitor_table.setRowCount(len(display_chain))
        ref_map = {opt["strikePrice"]: opt for opt in ref_chain}
        
        for r, opt in enumerate(display_chain):
            strike = opt["strikePrice"]
            ref_opt = ref_map.get(strike)
            
            if ref_opt:
                ce_oi_diff = opt["CE"]["OI"] - ref_opt["CE"]["OI"]
                ce_ltp_diff = round(opt["CE"]["LTP"] - ref_opt["CE"]["LTP"], 2)
                pe_ltp_diff = round(opt["PE"]["LTP"] - ref_opt["PE"]["LTP"], 2)
                pe_oi_diff = opt["PE"]["OI"] - ref_opt["PE"]["OI"]
            else:
                ce_oi_diff = ce_ltp_diff = pe_ltp_diff = pe_oi_diff = 0

            bg_color = QColor(0, 255, 149, 38) if opt.get("isATM") else QColor("#1a1a1a")
            
            ce_oi_str = f"{'+' if ce_oi_diff > 0 else ''}{ce_oi_diff}"
            ce_ltp_str = f"{'+' if ce_ltp_diff > 0 else ''}{ce_ltp_diff:.2f}"
            pe_ltp_str = f"{'+' if pe_ltp_diff > 0 else ''}{pe_ltp_diff:.2f}"
            pe_oi_str = f"{'+' if pe_oi_diff > 0 else ''}{pe_oi_diff}"

            cells_data = [
                (ce_oi_str, QColor("#00ff95") if ce_oi_diff > 0 else (QColor("#ff4d4d") if ce_oi_diff < 0 else QColor("#e0e0e0"))),
                (ce_ltp_str, QColor("#00ff95") if ce_ltp_diff > 0 else (QColor("#ff4d4d") if ce_ltp_diff < 0 else QColor("#e0e0e0"))),
                (str(strike), QColor("#ffffff")),
                (pe_ltp_str, QColor("#00ff95") if pe_ltp_diff > 0 else (QColor("#ff4d4d") if pe_ltp_diff < 0 else QColor("#e0e0e0"))),
                (pe_oi_str, QColor("#00ff95") if pe_oi_diff > 0 else (QColor("#ff4d4d") if pe_oi_diff < 0 else QColor("#e0e0e0")))
            ]
            
            for c, (text, fg_color) in enumerate(cells_data):
                item = self._get_or_create_item(self.monitor_table, r, c)
                item.setText(text)
                item.setForeground(QBrush(fg_color))
                item.setBackground(QBrush(bg_color))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def _refresh_auxiliary_tables_if_needed(self):
        now_ts = time.monotonic()
        if now_ts - self.last_aux_refresh_ts < 5:
            return

        self.refresh_alerts_table()
        self.last_aux_refresh_ts = now_ts

    def refresh_alerts_table(self):
        """Reads alert.csv and updates the bottom table."""
        alerts = []
        # Note: Your notifier.py saves to 'alert.csv', ensure name matches
        if os.path.exists('alert.csv'):
            with open('alert.csv', mode='r', encoding='utf-8') as f:
                reader = list(csv.reader(f))
                # Get last 5 alerts, newest first
                alerts = reader[-5:][::-1]
        else:
            self.alerts_table.setRowCount(0)
            return

        self.alerts_table.setRowCount(len(alerts))
        for r, row_data in enumerate(alerts):
            for c, text in enumerate(row_data):
                item = self._get_or_create_item(self.alerts_table, r, c)
                item.setText(text)
                
                # Color code the pattern column
                if c == 2:
                    color = QColor("#00ff95") if "UP" in text else QColor("#ff4d4d")
                    item.setForeground(QBrush(color))

    def setup_settings_tab(self):
        layout = QVBoxLayout(self.settings_tab)
        
        layout.addWidget(QLabel("Kite Zerodha API Settings"))
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter API Key")
        self.api_key_input.setText(config.API_KEY)
        layout.addWidget(self.api_key_input)
        
        self.api_secret_input = QLineEdit()
        self.api_secret_input.setPlaceholderText("Enter API Secret")
        self.api_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.api_secret_input)
        
        self.login_btn = QPushButton("🔑 LOGIN TO KITE")
        self.login_btn.clicked.connect(self.handle_kite_login)
        layout.addWidget(self.login_btn)
        
        self.auth_status = QLabel("Status: Not Authenticated")
        layout.addWidget(self.auth_status)
        layout.addStretch()

    def handle_kite_login(self):
        login_url = self.kite_auth.get_login_url()
        
        # 1. Show the URL to the user
        QMessageBox.information(self, "Kite Login", 
            f"Please log in here:\n\n{login_url}\n\nAfter logging in, you will be redirected to a URL. Copy the 'request_token' from that URL.")
        
        # 2. Get the request_token from the user
        token, ok = QInputDialog.getText(self, "Request Token", "Paste the request_token here:")
        
        if ok and token:
            access_token = self.kite_auth.generate_session(token)
            if access_token:
                self.auth_status.setText("Status: Authenticated ✅")
                self.kite_instance = self.kite_auth.kite

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StockHawkDesktop()
    window.show()
    sys.exit(app.exec())
