import os
import firebase_admin
from firebase_admin import credentials, firestore, storage
import sys

# Surgical Test for Firebase Storage Bridge
CRED_PATH = "/Users/shivamagent/Desktop/Style-Matcher/batch-backend-v2/firebase-service-account.json"
BUCKET_NAME = "style-matcher-9480d.appspot.com"
TEST_FILE = "/Users/shivamagent/Desktop/Style-Matcher/chaos_test_assets/For RLHF input/BON02248_rlhf.jpg"

def test_bridge():
    print(f"🔍 Testing Firebase Initializtion with {CRED_PATH}")
    if not os.path.exists(CRED_PATH):
        print("❌ Credential file missing!")
        return

    cred = credentials.Certificate(CRED_PATH)
    firebase_admin.initialize_app(cred, {'storageBucket': BUCKET_NAME})
    
    try:
        bucket = storage.bucket()
        print(f"🟢 Bucket found: {bucket.name}")
        
        if not os.path.exists(TEST_FILE):
            print(f"❌ Test file missing: {TEST_FILE}")
            return

        print(f"📤 Attempting upload of {TEST_FILE}...")
        blob = bucket.blob("tests/surgical_test.jpg")
        blob.upload_from_filename(TEST_FILE)
        
        print("🌍 Making public...")
        blob.make_public()
        print(f"✅ Success! URL: {blob.public_url}")
        
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    test_bridge()
