import os
from google.cloud import storage
from google.oauth2 import service_account

# Surgical Test to find the correct bucket
CRED_PATH = "/Users/shivamagent/Desktop/Style-Matcher/batch-backend-v2/firebase-service-account.json"

def find_buckets():
    print(f"🔍 Listing buckets for {CRED_PATH}")
    if not os.path.exists(CRED_PATH):
        print("❌ Credential file missing!")
        return

    try:
        credentials = service_account.Credentials.from_service_account_file(CRED_PATH)
        client = storage.Client(credentials=credentials, project="style-matcher-9480d")
        
        buckets = list(client.list_buckets())
        if not buckets:
            print("❌ No buckets found for this account/project.")
        else:
            print(f"✅ Found {len(buckets)} buckets:")
            for b in buckets:
                print(f"   - {b.name}")
                
    except Exception as e:
        print(f"❌ Failed to list buckets: {e}")

if __name__ == "__main__":
    find_buckets()
