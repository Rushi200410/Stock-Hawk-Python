# Stock Hawk Engine

This project is a small market-data simulator and pattern checker.

It generates a new snapshot every 5 seconds, stores the raw JSON output in `snapshots/`, and then analyzes the most recent history for simple breakout signals.

## What It Does

- Generates mock market prices for the symbols listed in `config.py`
- Saves each run as a timestamped JSON file
- Reads the latest snapshot history and checks for new highs or lows
- Sends Telegram alerts when a pattern is detected

## Project Flow

1. `main.py` starts the continuous loop.
2. `mock_generator.py` creates a new market snapshot.
3. `snapshot.py` writes the snapshot JSON file into `snapshots/`.
4. `hawk_engine.py` loads recent snapshots and compares prices.
5. `notifier.py` sends a Telegram message if a pattern is found.

## Temporary Data

The `snapshots/` folder is intentionally temporary for now.

It is used to collect data for analysis, and the files are generated automatically at runtime. Because of that, the folder is ignored by Git and should stay local to your machine.

## Files

- `main.py` - entry point for the running loop
- `mock_generator.py` - creates simulated market data
- `snapshot.py` - saves JSON snapshots
- `hawk_engine.py` - analyzes recent snapshots
- `notifier.py` - sends Telegram alerts
- `config.py` - stores symbols, intervals, and API settings

## Running The Project

Make sure Python dependencies are installed, then run:

```bash
python main.py
```

The simulator will keep running until you stop it manually.

## Notes

- If you later decide to keep the generated snapshots for version control, remove `snapshots/` from `.gitignore`.
- If `snapshots/` was already tracked by Git before being ignored, you will need to untrack it once from the index.

