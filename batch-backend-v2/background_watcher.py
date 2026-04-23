import os
import time
import json
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Local setup
SOURCE_ROOT = os.getenv("SOURCE_ROOT", "/Users/shivamagent/Pictures/RAW_Library")
QUEUE_FILE = os.path.join(os.path.dirname(__file__), "batch_queue.json")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class BackgroundFolderHandler(FileSystemEventHandler):
    """
    Monitors SOURCE_ROOT for new folders/files.
    Adds unique directories to the silent batch queue.
    """
    def __init__(self, queue_file):
        self.queue_file = queue_file

    def on_created(self, event):
        self._add_to_queue(event.src_path)

    def on_moved(self, event):
        self._add_to_queue(event.dest_path)

    def _add_to_queue(self, path):
        # We only care about directories or files that imply a new folder
        p = Path(path)
        target_dir = str(p if p.is_dir() else p.parent)
        
        if not os.path.isdir(target_dir):
            return

        # Load existing queue
        queue = []
        if os.path.exists(self.queue_file):
            try:
                with open(self.queue_file, "r") as f:
                    queue = json.load(f)
            except:
                queue = []

        # Logic: Only add if not already in queue and not currently processing
        # We use a simple list of dicts: {"folder": path, "priority": "background", "status": "pending"}
        if not any(item['folder'] == target_dir for item in queue):
            logging.info(f"📁 New folder detected: {target_dir}. Adding to silent queue.")
            queue.append({
                "folder": target_dir,
                "priority": "background",
                "status": "pending",
                "added_at": time.time()
            })
            
            with open(self.queue_file, "w") as f:
                json.dump(queue, f, indent=4)

if __name__ == "__main__":
    # Reload from environment in case main.py updated it
    source_root = os.getenv("SOURCE_ROOT", "/Users/shivamagent/Pictures/RAW_Library")
    if not os.path.exists(source_root):
        os.makedirs(source_root, exist_ok=True)
        
    event_handler = BackgroundFolderHandler(QUEUE_FILE)
    observer = Observer()
    observer.schedule(event_handler, source_root, recursive=True)
    
    logging.info(f"📡 Silent Watcher active on: {source_root}")
    observer.start()
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
