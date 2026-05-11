import sys
import os
import csv
import json
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QSpinBox, QComboBox, QPushButton,
                             QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
                             QLineEdit)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor, QBrush, QFont

import hawk_engine
import config
import mock_generator
from snapshot import cleanup_old_files

class StockHawkDesktop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🦅 StockHawk Desktop Terminal")
        self.resize(1000, 750)
        
        self.init_ui()
        
        # Start the background timer to fetch snapshots without freezing UI
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(config.FETCH_INTERVAL * 1000)
        
        # Heartbeat Timer (Simulation & Analysis)
        self.heartbeat = QTimer(self)
        self.heartbeat.timeout.connect(self.run_engine_step)
        self.heartbeat.start(config.FETCH_INTERVAL * 1000)
        
        self.current_interval_minutes = 0
        self.last_milestone_time = datetime.now()
        
        # Clock Timer (ticks every 1 second)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        
        # Initial data load
        self.run_engine_step()
        self.update_data()
        self.update_clock()

    def update_clock(self):
        """Updates the real-time clock display."""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.clock_label.setText(current_time)

    def run_engine_step(self):
        """Runs the background simulation and pattern checking."""
        import mock_generator
        from snapshot import cleanup_old_files
        
        mock_generator.start_simulation_once()
        hawk_engine.check_for_patterns()
        cleanup_old_files()
        
        # Check if it's time for a Milestone Report
        if self.current_interval_minutes > 0:
            now = datetime.now()
            diff = (now - self.last_milestone_time).total_seconds() / 60
            
            if diff >= self.current_interval_minutes:
                self.generate_interval_report()
                self.last_milestone_time = now

    def update_interval_settings(self, text):
        if text == "OFF":
            self.current_interval_minutes = 0
        else:
            self.current_interval_minutes = int(text.split(" ")[0])
            self.last_milestone_time = datetime.now()
            print(f"⏱️ Milestone interval set to {self.current_interval_minutes} minutes")

    def generate_interval_report(self):
        """Compares current price with the previous milestone."""
        history = hawk_engine.get_history(limit=1)
        if not history: return
        
        current_data = history[0]['data']
        from snapshot import save_milestone
        save_milestone(current_data, f"{self.current_interval_minutes}m")
        
        report_msg = hawk_engine.compare_milestones(current_data, self.current_interval_minutes)
        if report_msg:
            from notifier import send_master_alert
            send_master_alert(report_msg, symbol="MARKET", pattern=f"REPORT_{self.current_interval_minutes}M")

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
        
        # --- TAB 1: LIVE MARKET (Existing View) ---
        self.live_market_tab = QWidget()
        self.setup_live_market_tab()
        self.tabs.addTab(self.live_market_tab, "Live Market")

        # --- TAB 2: MONITORING PAGE (New View) ---
        self.monitoring_tab = QWidget()
        self.setup_monitoring_tab()
        self.tabs.addTab(self.monitoring_tab, "Monitoring")

        # --- TAB 3: SETTINGS (API Integration) ---
        self.settings_tab = QWidget()
        self.setup_settings_tab()
        self.tabs.addTab(self.settings_tab, "Settings")

        self.main_layout.addWidget(self.tabs)

    def setup_live_market_tab(self):
        layout = QVBoxLayout(self.live_market_tab)
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
        self.snap_spin.valueChanged.connect(self.update_data) # Instantly update when changed
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
        self.strike_spin.setRange(3, 10) # Min 3, Max 10
        self.strike_spin.setValue(10) # Default to your current view
        self.strike_spin.valueChanged.connect(self.update_data)
        control_layout.addWidget(self.strike_spin)
        
        # Symbol Selection
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(config.SYMBOLS)
        self.symbol_combo.currentTextChanged.connect(self.update_data) # Instantly update
        control_layout.addWidget(self.symbol_combo)
        
        # Expiry Selection
        self.expiry_combo = QComboBox()
        self.expiry_combo.addItem("24-MAY")
        control_layout.addWidget(self.expiry_combo)
        
        # Option Chain Button
        btn_chain = QPushButton("OPTION CHAIN")
        control_layout.addWidget(btn_chain)
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

        # --- MAIN TABLE (Options Chain) ---
        self.chain_label = QLabel("Options Chain (Live)")
        self.chain_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #00ff95;")
        layout.addWidget(self.chain_label)

        self.chain_table = QTableWidget(0, 7)
        self.chain_table.setHorizontalHeaderLabels([
            "CE OI", "CE Change", "CE LTP", "Strike", "PE LTP", "PE Change", "PE OI"
        ])
        self.chain_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.chain_table.verticalHeader().setVisible(False)
        self.chain_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.chain_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.chain_table, stretch=2)

    def setup_monitoring_tab(self):
        layout = QVBoxLayout(self.monitoring_tab)
        layout.setSpacing(20)
        
        # Monitoring Page focuses only on key changes and reports
        self.monitoring_label = QLabel("Interval-Based Trend Reports")
        self.monitoring_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #00ff95;")
        layout.addWidget(self.monitoring_label)
        
        # Add a table specifically for monitoring changes across intervals
        self.monitor_table = QTableWidget(0, 5)
        self.monitor_table.setHorizontalHeaderLabels(["Interval", "NIFTY Change", "BANKNIFTY Change", "PCR", "Sentiment"])
        self.monitor_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.monitor_table.verticalHeader().setVisible(False)
        self.monitor_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.monitor_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.monitor_table, stretch=2)

        # Keep the Alerts Table at the bottom of this page too
        alerts_label = QLabel("Recent Pattern Hits")
        alerts_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(alerts_label)
        
        self.alerts_table = QTableWidget(0, 4)
        self.alerts_table.setHorizontalHeaderLabels(["Time", "Symbol", "Pattern", "Message"])
        self.alerts_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.alerts_table.verticalHeader().setVisible(False)
        self.alerts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.alerts_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.alerts_table, stretch=1)

    def _get_or_create_item(self, table, row, col):
        """Helper to safely get or create table cells to avoid UI flickering."""
        item = table.item(row, col)
        if not item:
            item = QTableWidgetItem()
            table.setItem(row, col, item)
        return item

    def update_data(self):
        snap_count = self.snap_spin.value()
        history = hawk_engine.get_history(limit=snap_count + 1)
        if not history: return
        
        live_data = history[0]['data']
        sym = self.symbol_combo.currentText()
        
        if sym not in live_data: return
        current_chain = live_data[sym].get("optionsChain", [])
        self.chain_label.setText(f"{sym} Options Chain (Live) - ₹{live_data[sym]['price']}")
        
        # Calculate Metrics
        metrics = hawk_engine.calculate_market_metrics(current_chain)
        
        # Update Labels
        self.pcr_label.setText(f"PCR: {metrics['pcr']}")
        self.sentiment_label.setText(f"Sentiment: {metrics['sentiment']}")
        
        # Calculate True Change in OI
        if len(history) > 1:
            old_data = history[-1]['data']
            if sym in old_data:
                old_oi_map = {opt["strikePrice"]: {"CE_OI": opt["CE"]["OI"], "PE_OI": opt["PE"]["OI"]} for opt in old_data[sym].get("optionsChain", [])}
                for opt in current_chain:
                    strike = opt["strikePrice"]
                    opt["CE"]["changeInOI"] = opt["CE"]["OI"] - old_oi_map.get(strike, {"CE_OI": opt["CE"]["OI"]})["CE_OI"]
                    opt["PE"]["changeInOI"] = opt["PE"]["OI"] - old_oi_map.get(strike, {"PE_OI": opt["PE"]["OI"]})["PE_OI"]

        # --- NEW: Variable Strike Depth Logic ---
        num_strikes = self.strike_spin.value()
        
        # 1. Find the index of the ATM strike in the list
        atm_index = -1
        for i, opt in enumerate(current_chain):
            if opt.get("isATM"):
                atm_index = i
                break
        
        # 2. Slice the list based on your formula:
        # Rows Above = num_strikes
        # Rows Below = num_strikes - 1
        if atm_index != -1:
            start = max(0, atm_index - num_strikes)
            end = min(len(current_chain), atm_index + num_strikes)
            display_chain = current_chain[start:end]
        else:
            display_chain = current_chain # Fallback

        # --- Populate Option Chain Table (No Flicker) ---
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
                font = QFont(); font.setBold(bold); item.setFont(font)
                
        # --- 2. NEW: Update Alerts Table ---
        self.refresh_alerts_table()
        
        # --- 3. NEW: Update Monitor Table ---
        self.refresh_monitor_table()

    def refresh_monitor_table(self):
        """Populates the monitoring view with data from the milestones folder."""
        milestone_folder = config.MILESTONE_FOLDER
        if not os.path.exists(milestone_folder):
            return

        # 1. Get all milestone files and sort them by time (newest first)
        files = [f for f in os.listdir(milestone_folder) if f.endswith('.json')]
        files.sort(reverse=True) # Assuming filename has timestamp like YYYYMMDD_HHMM

        self.monitor_table.setRowCount(len(files))
        
        for r, filename in enumerate(files):
            try:
                with open(os.path.join(milestone_folder, filename), 'r') as f:
                    content = json.load(f)
                    m_type = content.get("type", "N/A")
                    data = content.get("data", {})
                    
                    # 2. Extract specific values for the table
                    # We'll calculate PCR on the fly using our engine
                    metrics = hawk_engine.calculate_market_metrics(data.get("BANKNIFTY", {}).get("optionsChain", []))
                    
                    # 3. Create items for each column
                    # Format: [Interval, NIFTY Price, BANKNIFTY Price, PCR, Sentiment]
                    nifty_price = f"₹{data.get('NIFTY', {}).get('price', 0)}"
                    bn_price = f"₹{data.get('BANKNIFTY', {}).get('price', 0)}"
                    
                    display_data = [
                        m_type, nifty_price, bn_price, 
                        str(metrics['pcr']), metrics['sentiment']
                    ]
                    
                    for c, text in enumerate(display_data):
                        item = self._get_or_create_item(self.monitor_table, r, c)
                        item.setText(text)
                        # Optional: Color code the sentiment
                        if c == 4:
                            color = QColor("#00ff95") if "Bullish" in text else QColor("#ff4d4d")
                            item.setForeground(QBrush(color))
            except Exception as e:
                print(f"Error loading milestone {filename}: {e}")

    def refresh_alerts_table(self):
        """Reads alert.csv and updates the bottom table."""
        alerts = []
        # Note: Your notifier.py saves to 'alert.csv', ensure name matches
        if os.path.exists('alert.csv'):
            with open('alert.csv', mode='r', encoding='utf-8') as f:
                reader = list(csv.reader(f))
                # Get last 5 alerts, newest first
                alerts = reader[-5:][::-1]

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
        # We'll wire this to the kite_worker flow in the next step
        self.auth_status.setText("Status: Pending Authentication...")
        print("Initiating Kite Connect Login...")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StockHawkDesktop()
    window.show()
    sys.exit(app.exec())