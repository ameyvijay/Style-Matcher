import firebase_admin
from firebase_admin import credentials, firestore
import os

def check_cloud_state():
    cred_path = "firebase-service-account.json"
    if not os.path.exists(cred_path):
        print(f"Error: Credentials not found at {cred_path}")
        return

    if not firebase_admin._apps:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)

    db = firestore.client()

    # 1. List all batches
    print("📋 [Cloud] All Batches:")
    batches = list(db.collection('batches').stream())
    for b in batches:
        print(f"   - {b.id}: {b.to_dict().get('status')} ({b.to_dict().get('total_photos')} photos)")

    # 2. Check current_active batch specifically
    active_ref = db.collection('batches').document('current_active')
    active_doc = active_ref.get()
    
    if active_doc.exists:
        data = active_doc.to_dict()
        batch_id = data.get('batch_id')
        print(f"🟢 [Cloud] current_active Batch: {batch_id}")
        
        # Check photos for THIS batch
        photos = list(db.collection('photos').where('batch_id', '==', batch_id).stream())
        print(f"📸 [Cloud] Photos in {batch_id}: {len(photos)}")
        for p in photos:
            p_data = p.to_dict()
            url_status = "✅ VALID URL" if p_data.get('rlhf_url') and "firebasestorage" in p_data.get('rlhf_url') else "❌ MISSING"
            print(f"   - {p.id}: {p_data.get('filename')} -> {url_status}")
            if p_data.get('rlhf_url'):
                print(f"     URL: {p_data.get('rlhf_url')[:60]}...")
    else:
        print("❌ [Cloud] current_active document NOT FOUND.")

    # 3. Last 5 photos added
    print("📸 [Cloud] Recent Photos (last 5):")
    recent_photos = db.collection('photos').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(5).stream()
    for p in recent_photos:
        p_data = p.to_dict()
        print(f"   - {p.id}: batch={p_data.get('batch_id')} status={p_data.get('status')} url={'set' if p_data.get('rlhf_url') else 'MISSING'}")

    all_pending = list(db.collection('photos').where('status', '==', 'pending').stream())
    print(f"🌍 [Cloud] Global Pending Photo Count: {len(all_pending)}")

if __name__ == "__main__":
    check_cloud_state()
