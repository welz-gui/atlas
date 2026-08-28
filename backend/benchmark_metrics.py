import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.domain import Base, Project, Organization, RegulatoryRule
from app.services.metrics import ai_metrics
from app.core.config import settings
from app.regulatory.jurisdiction import applicable_jurisdictions

engine = create_engine(settings.DATABASE_URL)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def setup_data(db):
    org = Organization(id="org1", name="Test Org")
    db.add(org)

    # 100 projects in the organization
    for i in range(100):
        project = Project(id=f"proj{i}", organization_id="org1", name=f"Project {i}", city_ibge=f"city{i%10}")
        db.add(project)

    db.commit()

def run_benchmark():
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(Organization).delete()
        setup_data(db)

        start = time.time()
        for _ in range(50):
            ai_metrics(db, "org1")
        end = time.time()
        print(f"Time taken for 50 iterations: {end - start} seconds")
    finally:
        db.close()

if __name__ == "__main__":
    run_benchmark()
