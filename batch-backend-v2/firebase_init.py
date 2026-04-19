"""
Antigravity Engine — Firebase Singleton
Provides safe, idempotent initialization of the Firebase Admin SDK.

Usage:
    from firebase_init import initialize_firebase
    initialize_firebase()

Environment Variables:
    FIREBASE_SERVICE_ACCOUNT_PATH  — Path to the service account JSON (default: ./firebase-service-account.json)
    FIREBASE_STORAGE_BUCKET        — GCS bucket name (e.g. style-matcher-9480d.firebasestorage.app)
"""
import os
import firebase_admin
from firebase_admin import credentials


def initialize_firebase() -> firebase_admin.App:
    """
    Singleton initialization for Firebase Admin SDK.
    Safe to call multiple times — only initializes once.
    Reads credentials and bucket from the environment.
    """
    if not firebase_admin._apps:
        cred_path = os.getenv(
            "FIREBASE_SERVICE_ACCOUNT_PATH",
            "firebase-service-account.json"
        )
        bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")

        if not os.path.exists(cred_path):
            raise FileNotFoundError(
                f"[firebase_init] Service account not found at '{cred_path}'. "
                "Set FIREBASE_SERVICE_ACCOUNT_PATH in your environment."
            )

        cred = credentials.Certificate(cred_path)
        options = {}
        if bucket_name:
            options["storageBucket"] = bucket_name

        firebase_admin.initialize_app(cred, options)
        print(f"📡 [firebase_init] Firebase Admin SDK initialized. Bucket: {bucket_name or '(none)'}")

    return firebase_admin.get_app()
