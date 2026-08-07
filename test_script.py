from backend.app.core.config import Settings
import os

os.environ["ENVIRONMENT"] = "development"
s = Settings()
print(f"DEV SECRET_KEY: {s.SECRET_KEY}")
