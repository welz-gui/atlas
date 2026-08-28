from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event
from app.models.domain import Base, Project, Organization, RegulatoryRule
from app.services.metrics import ai_metrics
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def setup_data(db):
    org = Organization(id="org1", name="Test Org")
    db.add(org)
    # 50 projects
    for i in range(50):
        project = Project(id=f"proj{i}", organization_id="org1", name=f"Project {i}", city_ibge=f"city{i%10}")
        db.add(project)
    db.commit()

query_count = 0

@event.listens_for(engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    global query_count
    query_count += 1

def run_benchmark():
    global query_count
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(Organization).delete()
        setup_data(db)

        query_count = 0
        ai_metrics(db, "org1")
        print(f"Queries executed: {query_count}")
    finally:
        db.close()

if __name__ == "__main__":
    run_benchmark()
