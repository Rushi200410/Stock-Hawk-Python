import sys
import os
import csv
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QSpinBox, QComboBox, QPushButton,
                             QTableWidget, QTableWidgetItem, QHeaderView)
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

    def init_ui(self):
        # Main Container
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

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
        """)

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
        
        main_layout.addLayout(control_layout)

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
        
        main_layout.addLayout(stats_layout)

        # --- MAIN TABLE (Options Chain) ---
        self.chain_label = QLabel("Options Chain (Live)")
        self.chain_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #00ff95;")
        main_layout.addWidget(self.chain_label)

        self.chain_table = QTableWidget(0, 7)
        self.chain_table.setHorizontalHeaderLabels([
            "CE OI", "CE Change", "CE LTP", "Strike", "PE LTP", "PE Change", "PE OI"
        ])
        self.chain_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.chain_table.verticalHeader().setVisible(False)
        self.chain_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.chain_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        main_layout.addWidget(self.chain_table, stretch=2)

        # --- ALERTS TABLE ---
        alerts_label = QLabel("Recent Pattern Hits")
        alerts_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        main_layout.addWidget(alerts_label)
        
        self.alerts_table = QTableWidget(0, 4)
        self.alerts_table.setHorizontalHeaderLabels(["Time", "Symbol", "Pattern", "Message"])
        self.alerts_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.alerts_table.verticalHeader().setVisible(False)
        self.alerts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.alerts_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        main_layout.addWidget(self.alerts_table, stretch=1)

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

        # --- Populate Option Chain Table (No Flicker) ---
        self.chain_table.setRowCount(len(current_chain))
        for r, opt in enumerate(current_chain):
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StockHawkDesktop()
    window.show()
    sys.exit(app.exec())