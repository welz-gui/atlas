from app.core.database import SessionLocal
from backend.stage0_report import generate_stage0_report

if __name__ == "__main__":
    generate_stage0_report()
