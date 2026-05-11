import os
import csv
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import uvicorn

import hawk_engine
import config
import mock_generator
from snapshot import cleanup_old_files

async def market_simulation_loop():
    """Background loop to replace main.py and run everything from one place."""
    while True:
        mock_generator.start_simulation_once()
        hawk_engine.check_for_patterns()
        cleanup_old_files()
        await asyncio.sleep(config.FETCH_INTERVAL)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(market_simulation_loop())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

def get_recent_alerts(limit=10):
    alerts = []
    if not os.path.exists('alert.csv'):
        return alerts
    with open('alert.csv', mode='r') as f:
        reader = list(csv.reader(f))
        alerts = reader[-limit:][::-1]
    return alerts

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>StockHawk Dashboard</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f0f0f; color: #e0e0e0; padding: 30px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .card { background: #1a1a1a; padding: 20px; border-radius: 12px; border: 1px solid #333; }
        h1 { color: #00ff95; margin-bottom: 30px; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #333; }
        th { color: #888; text-transform: uppercase; font-size: 12px; }
        .bullish { color: #00ff95; font-weight: bold; }
        .bearish { color: #ff4d4d; font-weight: bold; }
        .price-val { font-size: 1.5em; color: #fff; font-weight: bold; }
        .symbol-name { font-size: 1.2em; }
    </style>
</head>
<body>
    <h1>🦅 StockHawk Real-Time Dashboard</h1>
    <div class="grid">
        <!-- CONTROL PANEL -->
        <div class="card" style="grid-column: span 2; display: flex; gap: 20px; align-items: center; background: #252525;">
            <div id="status-light" style="width: 15px; height: 15px; background: #00ff95; border-radius: 50%;"></div>
            <span style="font-weight: bold; color: #00ff95;">CONNECTED</span>
            
            <label>Snapshots:</label>
            <input type="number" id="snap-count" value="10" style="width: 50px; background: #333; color: white; border: 1px solid #555;">
            
            <select id="symbol-select" style="background: #333; color: white; padding: 5px;">
                <option value="NIFTY">NIFTY</option>
                <option value="BANKNIFTY">BANKNIFTY</option>
            </select>
            
            <select id="expiry-select" style="background: #333; color: white; padding: 5px;">
                <option value="26-MAY">26-MAY</option>
            </select>
            
            <button style="background: #00ff95; color: black; border: none; padding: 5px 15px; font-weight: bold; cursor: pointer;">OPTION CHAIN</button>
        </div>

        <!-- LIVE PRICES SECTION -->
        <div class="card">
            <h3>Live Prices</h3>
            <div id="prices-container">
                <p>Loading prices...</p>
            </div>
        </div>

        <!-- RECENT ALERTS SECTION -->
        <div class="card" style="grid-column: span 2;">
            <h3>Recent Pattern Hits</h3>
            <table>
                <thead>
                    <tr><th>Time</th><th>Symbol</th><th>Pattern</th><th>Message</th></tr>
                </thead>
                <tbody id="alerts-tbody">
                    <tr><td colspan="4">Loading alerts...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- OPTIONS CHAIN SECTION -->
        <div class="card" style="grid-column: span 2;">
            <h3 id="options-title">NIFTY Options Chain (Live)</h3>
            <table>
                <thead>
                    <tr>
                        <th>CE OI</th><th>CE Change</th><th>CE LTP</th>
                        <th style="text-align:center;">Strike</th>
                        <th>PE LTP</th><th>PE Change</th><th>PE OI</th>
                    </tr>
                </thead>
                <tbody id="options-tbody">
                    <tr><td colspan="7">Loading chain...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        // 1. Open the "Pipe" to Python
        const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
        const ws = new WebSocket(`${wsProtocol}://${window.location.host}/ws`);
        
        let currentSymbol = "NIFTY";

        function sendState(payload) {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify(payload));
            }
        }

        document.getElementById("symbol-select").addEventListener("change", (e) => {
            currentSymbol = e.target.value;
            sendState({ symbol: currentSymbol });
            document.getElementById("options-title").innerText = `${currentSymbol} Options Chain (Live)`;
        });

        document.getElementById("snap-count").addEventListener("change", (e) => {
            sendState({ snapshots: parseInt(e.target.value) });
        });

        // 2. Listen for JSON packets
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            
            // Update Live Prices
            if (data.prices) {
                const pricesContainer = document.getElementById("prices-container");
                pricesContainer.innerHTML = ""; // Clear old
                for (const [sym, details] of Object.entries(data.prices)) {
                    const div = document.createElement("div");
                    div.style.marginBottom = "15px";
                    div.innerHTML = `<span class="symbol-name">${sym}</span>: <span class="price-val">₹${details.price}</span>`;
                    pricesContainer.appendChild(div);
                }
                
                // Update Options Chain for Active Symbol
                const activeSymbol = data.current_symbol || currentSymbol;
                if (data.prices[activeSymbol] && data.prices[activeSymbol].optionsChain) {
                    const optionsTbody = document.getElementById("options-tbody");
                    optionsTbody.innerHTML = ""; 
                    data.prices[activeSymbol].optionsChain.forEach(opt => {
                        const tr = document.createElement("tr");
                        if (opt.isATM) {
                            tr.style.backgroundColor = "rgba(0, 255, 149, 0.15)";
                        }
                        tr.innerHTML = `
                            <td>${opt.CE.OI}</td>
                            <td class="${opt.CE.changeInOI > 0 ? 'bullish' : 'bearish'}">${opt.CE.changeInOI}</td>
                            <td>₹${opt.CE.LTP}</td>
                            <td style="font-weight: bold; text-align: center; color: #fff;">${opt.strikePrice}</td>
                            <td>₹${opt.PE.LTP}</td>
                            <td class="${opt.PE.changeInOI > 0 ? 'bullish' : 'bearish'}">${opt.PE.changeInOI}</td>
                            <td>${opt.PE.OI}</td>
                        `;
                        optionsTbody.appendChild(tr);
                    });
                }
            }
            
            // Update Alerts
            if (data.alerts) {
                const alertsTbody = document.getElementById("alerts-tbody");
                alertsTbody.innerHTML = ""; // Clear old
                data.alerts.forEach(alert => {
                    const tr = document.createElement("tr");
                    const patternClass = alert[2].includes("UP") ? "bullish" : "bearish";
                    tr.innerHTML = `
                        <td>${alert[0]}</td>
                        <td>${alert[1]}</td>
                        <td class="${patternClass}">${alert[2]}</td>
                        <td>${alert[3]}</td>
                    `;
                    alertsTbody.appendChild(tr);
                });
            }
        };
        
        ws.onclose = () => {
            const light = document.getElementById("status-light");
            light.style.background = "#ff4d4d";
            light.nextElementSibling.innerText = "DISCONNECTED";
            light.nextElementSibling.style.color = "#ff4d4d";
        };
    </script>
</body>
</html>
"""

@app.get("/")
async def get():
    """Sends the HTML page to the browser once."""
    return HTMLResponse(HTML_TEMPLATE)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # This 'state' keeps track of what the user is clicking in the browser
    state = {"symbol": "NIFTY", "snap_count": 10}
    
    async def listen_for_browser_messages():
        """Listens for when you change the dropdown or snap count in the UI."""
        try:
            while True:
                # Receive message from JavaScript (the browser)
                data = await websocket.receive_json()
                if "symbol" in data:
                    state["symbol"] = data["symbol"]
                    print(f"Browser changed symbol to: {state['symbol']}")
                if "snapshots" in data:
                    state["snap_count"] = max(1, int(data["snapshots"]))
                    print(f"Browser changed snapshots to: {state['snap_count']}")
        except Exception as e:
            print(f"WebSocket Receiver Error: {e}")

    async def broadcast_live_data():
        """Pushes data from Python to the browser every few seconds."""
        try:
            while True:
                # 1. Fetch latest data (limit based on user input)
                history = hawk_engine.get_history(limit=state["snap_count"] + 1)
                live_data = history[0]['data'] if history else {}
                
                # Phase 12: Calculating "True" Change in OI
                if live_data and len(history) > 1:
                    old_data = history[-1]['data'] # The data from X snapshots ago
                    for sym in config.SYMBOLS:
                        if sym in live_data and sym in old_data:
                            current_chain = live_data[sym].get("optionsChain", [])
                            old_chain = old_data[sym].get("optionsChain", [])
                            
                            old_oi_map = {
                                opt["strikePrice"]: {"CE_OI": opt["CE"]["OI"], "PE_OI": opt["PE"]["OI"]} 
                                for opt in old_chain
                            }
                            
                            for opt in current_chain:
                                strike = opt["strikePrice"]
                                if strike in old_oi_map:
                                    opt["CE"]["changeInOI"] = opt["CE"]["OI"] - old_oi_map[strike]["CE_OI"]
                                    opt["PE"]["changeInOI"] = opt["PE"]["OI"] - old_oi_map[strike]["PE_OI"]
                                else:
                                    opt["CE"]["changeInOI"] = 0
                                    opt["PE"]["changeInOI"] = 0

                alerts = get_recent_alerts(10)
                
                # 2. Send the packet to the browser
                await websocket.send_json({
                    "prices": live_data,
                    "alerts": alerts,
                    "current_symbol": state["symbol"] # Tell UI which symbol is 'Active'
                })
                
                # Wait for the next interval (sync with simulator)
                await asyncio.sleep(config.FETCH_INTERVAL)
        except Exception as e:
            print(f"WebSocket Broadcaster Error: {e}")

    # Use asyncio.gather to run both 'Listen' and 'Broadcast' at the same time
    await asyncio.gather(listen_for_browser_messages(), broadcast_live_data())

if __name__ == "__main__":
    # We use Uvicorn to run FastAPI
    uvicorn.run(app, host="0.0.0.0", port=5000)
