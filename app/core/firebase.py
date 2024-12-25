# app/core/firebase.py
import firebase_admin
from firebase_admin import credentials, auth
from functools import lru_cache
from ..config.settings import settings

# Initialize Firebase Admin
cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
firebase_admin.initialize_app(cred)

@lru_cache()
def get_firebase_admin():
    return auth