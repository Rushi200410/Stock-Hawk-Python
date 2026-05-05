import os
import json
import time
from datetime import datetime
import config

class SnapshotManager:
    def __init__(self):
        self.folder = config.SNAPSHOT_FOLDER
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)

    def save(self, data):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snap_{timestamp}.json"
        filepath = os.path.join(self.folder, filename)
        
        payload = {
            "timestamp": timestamp,
            "data": data
        }
        
        with open(filepath, "w") as f:
            json.dump(payload, f, indent=2)
        return filepath

def cleanup_old_snapshots(days=7):
    """Deletes snapshots older than the specified number of days."""
    now = time.time()
    # 7 days in seconds
    max_age = days * 24 * 60 * 60 
    
    for f in os.listdir(config.SNAPSHOT_FOLDER):
        path = os.path.join(config.SNAPSHOT_FOLDER, f)
        if os.stat(path).st_mtime < (now - max_age):
            os.remove(path)
            print(f"🧹 Cleaned up old snapshot: {f}")

snapshot_manager = SnapshotManager()