from flask import Flask, jsonify, render_template_string
import hawk_engine
import config

app = Flask(__name__)

# This is the "HTML" code for your webpage
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>StockHawk Dashboard</title>
    <meta http-equiv="refresh" content="{{ config.FETCH_INTERVAL }}"> <!-- Auto-refresh every {{ config.FETCH_INTERVAL }} seconds -->
    <style>
        body { font-family: sans-serif; background: #121212; color: white; padding: 20px; }
        .card { background: #1e1e1e; padding: 20px; border-radius: 10px; margin-bottom: 10px; }
        .high { color: #4caf50; } .low { color: #f44336; }
    </style>
</head>
<body>
    <h1>🦅 StockHawk Real-Time Dashboard</h1>
    <div id="content">
        {% for sym, details in data.items() %}
        <div class="card">
            <h2>{{ sym }}: ₹{{ details.price }}</h2>
            <p>Last Update: {{ details.time }}</p>
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    # Load the latest data from our snapshots
    history = hawk_engine.get_history(limit=1)
    if not history:
        return "<h1>Loading data...</h1>"
    
    latest_data = history[0]['data']
    return render_template_string(HTML_TEMPLATE, data=latest_data)

if __name__ == "__main__":
    app.run(port=5000)