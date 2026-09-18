import time
from app.core.database import SessionLocal
from app.models.domain import Organization, Project, AnalysisRun, ValidationRecord
from stage0_report import generate_stage0_report

# We will run just the specific query multiple times to measure the impact
db = SessionLocal()
org = db.query(Organization).filter(Organization.name.like("%Concierge%")).first()
if not org:
    # Need to create mock data
    pass
