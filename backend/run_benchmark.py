import time
import uuid
import sys
from app.core.database import SessionLocal, Base, engine
from app.models.domain import Organization, Project, AnalysisRun, ValidationRecord
from sqlalchemy import create_engine
from sqlalchemy import func
from sqlalchemy.orm import load_only

# Need to run migrations or create tables if we're using in-memory / testing db
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Mock data creation to test performance
def seed_data(db):
    try:
        org = Organization(id=str(uuid.uuid4()), name="Concierge Benchmark Org")
        db.add(org)

        projects = []
        for i in range(100): # 100 projects
            proj = Project(id=str(uuid.uuid4()), organization_id=org.id, name=f"Proj {i}")
            projects.append(proj)
            db.add(proj)

        db.commit()

        for p in projects:
            for j in range(5): # 5 analysis runs per project
                run = AnalysisRun(id=str(uuid.uuid4()), project_id=p.id, organization_id=org.id, jurisdiction="BR-RS-4311403", catalog_version="1.0", engine_version="1.0")
                db.add(run)
                db.commit()

                records = []
                for k in range(500): # 500 records per run -> total 250,000
                    record = ValidationRecord(
                        id=str(uuid.uuid4()),
                        organization_id=org.id,
                        project_id=p.id,
                        analysis_run_id=run.id,
                        rule_id=f"rule_{k}",
                        rule_title=f"Rule {k}",
                        field=f"Field {k}",
                        expected_value="yes",
                        actual_value="no",
                        rule_state="vigente",
                        severity="high",
                        status="conforme" if k % 2 == 0 else ("nao_conforme" if k % 3 == 0 else "nao_verificavel")
                    )
                    records.append(record)
                db.add_all(records)
                db.commit()
        return org, projects
    except Exception as e:
        db.rollback()
        print("Error seeding:", e)
        return None, None

def test_original(db, projects):
    start = time.time()
    val_records = db.query(ValidationRecord).filter(
        ValidationRecord.analysis_run_id.in_(
            db.query(AnalysisRun.id).filter(AnalysisRun.project_id.in_([p.id for p in projects]))
        )
    ).all()
    nao_verificaveis = sum(1 for v in val_records if v.status == "nao_verificavel")
    bloqueios = sum(1 for v in val_records if v.status == "nao_conforme")
    conformes = sum(1 for v in val_records if v.status == "conforme")
    end = time.time()
    return end - start, len(val_records), nao_verificaveis

def test_optimized_direct(db, projects):
    start = time.time()
    val_records = db.query(ValidationRecord).filter(
        ValidationRecord.project_id.in_([p.id for p in projects])
    ).all()
    nao_verificaveis = sum(1 for v in val_records if v.status == "nao_verificavel")
    bloqueios = sum(1 for v in val_records if v.status == "nao_conforme")
    conformes = sum(1 for v in val_records if v.status == "conforme")
    end = time.time()
    return end - start, len(val_records), nao_verificaveis

def test_optimized_direct_load_only(db, projects):
    start = time.time()
    val_records = db.query(ValidationRecord).filter(
        ValidationRecord.project_id.in_([p.id for p in projects])
    ).options(load_only(ValidationRecord.status)).all()
    nao_verificaveis = sum(1 for v in val_records if v.status == "nao_verificavel")
    bloqueios = sum(1 for v in val_records if v.status == "nao_conforme")
    conformes = sum(1 for v in val_records if v.status == "conforme")
    end = time.time()
    return end - start, len(val_records), nao_verificaveis

def test_optimized_db_group_by(db, projects):
    start = time.time()
    results = db.query(
        ValidationRecord.status,
        func.count(ValidationRecord.id)
    ).filter(
        ValidationRecord.project_id.in_([p.id for p in projects])
    ).group_by(ValidationRecord.status).all()

    counts = dict(results)
    nao_verificaveis = counts.get("nao_verificavel", 0)
    bloqueios = counts.get("nao_conforme", 0)
    conformes = counts.get("conforme", 0)

    total = sum(counts.values())
    end = time.time()
    return end - start, total, nao_verificaveis

org, projects = seed_data(db)
if not org:
    org = db.query(Organization).first()
    projects = db.query(Project).filter_by(organization_id=org.id).all() if org else []

if not projects:
    print("No projects found, exiting.")
    sys.exit(1)

print("Warming up...")
test_original(db, projects)
test_optimized_direct(db, projects)
test_optimized_direct_load_only(db, projects)
test_optimized_db_group_by(db, projects)

orig_times = []
direct_times = []
load_only_times = []
db_group_by_times = []

for _ in range(3):
    t_orig, count_orig, nv_orig = test_original(db, projects)
    orig_times.append(t_orig)

    t_dir, count_dir, nv_dir = test_optimized_direct(db, projects)
    direct_times.append(t_dir)

    t_lo, count_lo, nv_lo = test_optimized_direct_load_only(db, projects)
    load_only_times.append(t_lo)

    t_db, count_db, nv_db = test_optimized_db_group_by(db, projects)
    db_group_by_times.append(t_db)

print(f"Original: {sum(orig_times)/len(orig_times):.4f}s")
print(f"Optimized (Direct): {sum(direct_times)/len(direct_times):.4f}s")
print(f"Optimized (Direct load_only): {sum(load_only_times)/len(load_only_times):.4f}s")
print(f"Optimized (DB Group By): {sum(db_group_by_times)/len(db_group_by_times):.4f}s")
print(f"Counts Original: {count_orig}, NV: {nv_orig}")
print(f"Counts Optimized (DB Group By): {count_db}, NV: {nv_db}")

# Clean up
if org and org.name == "Concierge Benchmark Org":
    for p in projects:
        runs = db.query(AnalysisRun).filter_by(project_id=p.id).all()
        for r in runs:
            db.query(ValidationRecord).filter_by(analysis_run_id=r.id).delete()
        db.query(AnalysisRun).filter_by(project_id=p.id).delete()
    db.query(Project).filter_by(organization_id=org.id).delete()
    db.delete(org)
    db.commit()
