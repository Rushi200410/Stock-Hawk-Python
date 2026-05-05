from flask import Flask, jsonify, render_template_string
import hawk_engine
import csv
import os
import config

app = Flask(__name__)

def get_recent_alerts(limit=10):
    """Reads the last few alerts from the CSV file."""
    alerts = []
    if not os.path.exists('alert.csv'):
        return alerts
    with open('alert.csv', mode='r') as f:
        reader = list(csv.reader(f))
        # Get the last 'limit' number of rows, reversed so newest is on top
        alerts = reader[-limit:][::-1]
    return alerts

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>StockHawk Dashboard</title>
    <meta http-equiv="refresh" content="{{ config.FETCH_INTERVAL }}"> <!-- Auto-refresh every {{ config.FETCH_INTERVAL }} seconds -->
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
    </style>
</head>
<body>
    <h1>🦅 StockHawk Real-Time Dashboard</h1>
    <div class="grid">
        <!-- LIVE PRICES SECTION -->
        <div class="card">
            <h3>Live Prices</h3>
            {% for sym, details in live_data.items() %}
            <div style="margin-bottom: 15px;">
                <span style="font-size: 1.2em;">{{ sym }}</span>: 
                <span style="font-size: 1.5em; color: #fff;">₹{{ details.price }}</span>
            </div>
            {% endfor %}
        </div>

        <!-- RECENT ALERTS SECTION -->
        <div class="card" style="grid-column: span 2;">
            <h3>Recent Pattern Hits</h3>
            <table>
                <thead>
                    <tr><th>Time</th><th>Symbol</th><th>Pattern</th><th>Message</th></tr>
                </thead>
                <tbody>
                    {% for alert in alerts %}
                    <tr>
                        <td>{{ alert[0] }}</td>
                        <td>{{ alert[1] }}</td>
                        <td class="{{ 'bullish' if 'UP' in alert[2] else 'bearish' }}">{{ alert[2] }}</td>
                        <td>{{ alert[3] }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    history = hawk_engine.get_history(limit=1)
    live_data = history[0]['data'] if history else {}
    alerts = get_recent_alerts(10)
    return render_template_string(HTML_TEMPLATE, live_data=live_data, alerts=alerts, config=config)

if __name__ == "__main__":
    app.run(port=5000)