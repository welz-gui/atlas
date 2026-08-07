from backend.app.core.config import Settings
import os

os.environ["ENVIRONMENT"] = "production"
try:
    s = Settings()
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")
