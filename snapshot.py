import os
import json
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

snapshot_manager = SnapshotManager()