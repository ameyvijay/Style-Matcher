import os
import json
import uuid
import random
from datetime import datetime
from pathlib import Path
from typing import List

from database import SessionLocal, Media, Annotation, DatasetSnapshot

def export_dataset(
    version_tag: str,
    export_dir: str = "./ml_datasets",
    split_ratios: tuple = (0.8, 0.1, 0.1)
) -> None:
    """
    Creates a DatasetSnapshot based on human annotations.
    Prevents contamination by locking exactly which media IDs belong to Train/Eval/Test.
    Creates symlinks in export_dir for easy DataLoader integration.
    """
    assert sum(split_ratios) == 1.0, "Split ratios must sum to 1.0"
    
    db = SessionLocal()
    
    # 1. Fetch all annotated Media (Cohen's Kappa / Ground Truth)
    # Here we simply grab any photo that has at least one human annotation.
    # A true pipeline would resolve disagreement here (if UserA says Keep, UserB says Cull).
    annotated_media_ids = db.query(Annotation.media_id).distinct().all()
    media_ids = [m[0] for m in annotated_media_ids]
    
    if not media_ids:
        print("❌ No annotated photos found in database. Please run RLHF first.")
        db.close()
        return

    # Shuffle for random splits
    random.seed(42) # Deterministic shuffle baseline
    random.shuffle(media_ids)
    
    total = len(media_ids)
    train_end = int(total * split_ratios[0])
    eval_end = train_end + int(total * split_ratios[1])
    
    splits = {
        "train": media_ids[:train_end],
        "eval": media_ids[train_end:eval_end],
        "test_golden": media_ids[eval_end:]
    }
    
    print(f"📊 Dataset Size: {total} photos")
    print(f"   Train: {len(splits['train'])}")
    print(f"   Eval: {len(splits['eval'])}")
    print(f"   Test: {len(splits['test_golden'])}")

    # 2. Prevent Snapshot Contamination (Lock in DB)
    for split_name, ids in splits.items():
        if not ids: continue
        
        snapshot = DatasetSnapshot(
            snapshot_version=f"{version_tag}_{split_name}",
            purpose=split_name,
            media_id_list=json.dumps(ids)
        )
        db.add(snapshot)
    
    db.commit()
    print("✅ Created immutable DatasetSnapshots in local database.")

    # 3. Create physical directory structure (Symlinks)
    base_export = os.path.join(export_dir, version_tag)
    os.makedirs(base_export, exist_ok=True)
    
    for split_name, ids in splits.items():
        if not ids: continue
        
        split_dir = os.path.join(base_export, split_name)
        
        # typically you'd have 'images' and 'labels', here we'll just sort into 'keeper' and 'cull'
        keeper_dir = os.path.join(split_dir, "keeper")
        cull_dir = os.path.join(split_dir, "cull")
        
        os.makedirs(keeper_dir, exist_ok=True)
        os.makedirs(cull_dir, exist_ok=True)
        
        # Symlink all photos
        for mid in ids:
            media = db.query(Media).filter(Media.id == mid).first()
            # Resolve the final action for this media
            # If multiple users, we'd do a majority vote here. Taking last for now.
            annotation = db.query(Annotation).filter(Annotation.media_id == mid).order_by(Annotation.id.desc()).first()
            
            if not media or not annotation: continue
            
            target_class_dir = keeper_dir if annotation.action == 'swipe_right_keeper' else cull_dir
            ext = os.path.splitext(media.file_path)[1]
            symlink_path = os.path.join(target_class_dir, f"{media.photo_hash}{ext}")
            
            try:
                if not os.path.exists(symlink_path):
                    os.symlink(media.file_path, symlink_path)
            except OSError as e:
                print(f"Error symlinking: {e}")
                
    db.close()
    print(f"✅ Exported Train/Eval symlinks locally to: {base_export}")


if __name__ == "__main__":
    import sys
    tag = sys.argv[1] if len(sys.argv) > 1 else f"dataset_v1.0_{int(datetime.now().timestamp())}"
    export_dataset(version_tag=tag)
