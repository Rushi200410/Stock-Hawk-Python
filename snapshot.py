import os
import json
import time
from datetime import datetime
import config
from app_logger import logger

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
            logger.info("Cleaned up old snapshot: %s", f)

snapshot_manager = SnapshotManager()

def cleanup_old_files():
    """Deletes files older than 24 hours."""
    now = time.time()
    for f in os.listdir(config.SNAPSHOT_FOLDER):
        path = os.path.join(config.SNAPSHOT_FOLDER, f)
        # 86400 seconds = 24 hours
        if os.stat(path).st_mtime < now - 86400:
            os.remove(path)
            logger.info("Janitor removed old file %s", f)


def save_milestone(data, interval_name):
    """Saves a snapshot to the permanent milestones folder."""
    if not os.path.exists(config.MILESTONE_FOLDER):
        os.makedirs(config.MILESTONE_FOLDER)
    
    # Use seconds + microseconds so repeated saves in the same minute do not overwrite each other.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{interval_name}_{timestamp}.json"
    filepath = os.path.join(config.MILESTONE_FOLDER, filename)
    
    with open(filepath, "w") as f:
        json.dump({"type": interval_name, "data": data}, f)
            
