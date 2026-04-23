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
        if not event.is_directory:
            ext = os.path.splitext(event.src_path)[1].lower()
            from models import IMAGE_EXTENSIONS
            if ext in IMAGE_EXTENSIONS:
                self._add_to_queue(os.path.dirname(event.src_path))
        else:
            self._add_to_queue(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            ext = os.path.splitext(event.dest_path)[1].lower()
            from models import IMAGE_EXTENSIONS
            if ext in IMAGE_EXTENSIONS:
                self._add_to_queue(os.path.dirname(event.dest_path))
        else:
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
                    content = json.load(f)
                    # If orchestrator uses a dict with 'photos' key, 
                    # we need to be careful. But orchestrator process_background_queue
                    # expects a simple list of dicts.
                    queue = content if isinstance(content, list) else []
            except:
                queue = []

        # Logic: Only add if not already in queue
        if not any(item.get('folder') == target_dir for item in queue if isinstance(item, dict)):
            logging.info(f"📁 New folder detected: {target_dir}. Adding to silent queue.")
            queue.append({
                "folder": target_dir,
                "priority": "background",
                "status": "pending",
                "added_at": time.time()
            })
            
            with open(self.queue_file, "w") as f:
                json.dump(queue, f, indent=4)

            # 🔔 Notify via Firebase
            try:
                from firebase_bridge import get_bridge
                bridge = get_bridge()
                bridge.send_push_notification(
                    title="New Shoot Detected",
                    body=f"Folder '{os.path.basename(target_dir)}' has been added to the processing queue.",
                    data={"type": "new_folder", "path": target_dir}
                )
            except Exception as e:
                logging.warning(f"Failed to send detection notification: {e}")

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
