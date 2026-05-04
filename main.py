import time
import mock_generator
import hawk_engine

if __name__ == "__main__":
    print("🦅 StockHawk Engine starting...")
    
    # This loop keeps the whole system running
    while True:
        # 1. Generate new fake data
        mock_generator.start_simulation_once() 
        
        # 2. Analyze the new data immediately
        hawk_engine.analyze_patterns()
        
        # 3. Wait for the next interval
        time.sleep(10)