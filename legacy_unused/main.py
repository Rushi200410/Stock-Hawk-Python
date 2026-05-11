import time
import mock_generator
import hawk_engine
import config
from snapshot import cleanup_old_files

if __name__ == "__main__":
    print("🦅 StockHawk Engine starting...")
    
    # This loop keeps the whole system running
    while True:
        # 1. Generate new fake data
        mock_generator.start_simulation_once() 
        
        # 2. Analyze the new data immediately
        hawk_engine.check_for_patterns()
        
        # 3. Clean up old snapshots (older than 24 hours)
        cleanup_old_files()
        
        # 4. Wait for the next interval
        time.sleep(config.FETCH_INTERVAL)