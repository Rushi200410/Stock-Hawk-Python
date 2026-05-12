import os
import json
import time
from datetime import datetime
import config

class SnapshotManager:
    def __init__(self):
        self.folder = config.SNAPSHOT_FOLDER
        os.makedirs(self.folder, exist_ok=True)

    def save(self, data):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snap_{timestamp}.json"
        filepath = os.path.join(self.folder, filename)
        
        payload = {
            "timestamp": timestamp,
            "data": data
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, separators=(",", ":"))
        return filepath

def cleanup_old_snapshots(days=7):
    """Deletes snapshots older than the specified number of days."""
    now = time.time()
    # 7 days in seconds
    max_age = days * 24 * 60 * 60

    if not os.path.exists(config.SNAPSHOT_FOLDER):
        return

    with os.scandir(config.SNAPSHOT_FOLDER) as entries:
        for entry in entries:
            if not entry.is_file():
                continue
            if entry.stat().st_mtime < (now - max_age):
                os.remove(entry.path)
                print(f"Cleaned up old snapshot: {entry.name}")

snapshot_manager = SnapshotManager()

def cleanup_old_files():
    """Deletes files older than 24 hours."""
    now = time.time()
    if not os.path.exists(config.SNAPSHOT_FOLDER):
        return

    with os.scandir(config.SNAPSHOT_FOLDER) as entries:
        for entry in entries:
            if not entry.is_file():
                continue
            # 86400 seconds = 24 hours
            if entry.stat().st_mtime < now - 86400:
                os.remove(entry.path)
                print(f"Janitor removed old file {entry.name}")


def save_milestone(data, interval_name):
    """Saves a snapshot to the permanent milestones folder."""
    os.makedirs(config.MILESTONE_FOLDER, exist_ok=True)
    
    # Use seconds + microseconds so repeated saves in the same minute do not overwrite each other.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{interval_name}_{timestamp}.json"
    filepath = os.path.join(config.MILESTONE_FOLDER, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"type": interval_name, "data": data}, f, separators=(",", ":"))
    return filepath
            
