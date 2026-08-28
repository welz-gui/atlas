import time
from sqlalchemy import create_engine, Column, String, JSON, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class ValidationRecord(Base):
    __tablename__ = "test_validation_records"
    id = Column(Integer, primary_key=True)
    organization_id = Column(String)
    analysis_run_id = Column(String)
    project_id = Column(String)
    rule_code = Column(String)
    rule_topic = Column(String)
    rule_description = Column(String)
    severity = Column(String)
    status = Column(String)
    evaluated_value = Column(String)
    is_publishable = Column(Boolean)

engine = create_engine("sqlite:///:memory:", echo=False)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

def run_test():
    db = SessionLocal()

    results = []
    for i in range(10000):
        results.append({
            "rule_code": f"RULE_{i}",
            "rule_topic": "TEST",
            "rule_description": "Test description which is a bit long to simulate string allocation.",
            "severity": "IMPEDITIVO",
            "status": "CONFORME",
            "evaluated_value": "100",
            "is_publishable": True,
        })

    # 1. Normal N+1 approach
    start_n1 = time.perf_counter()
    for result in results:
        db.add(
            ValidationRecord(
                organization_id="org1",
                analysis_run_id="run1",
                project_id="proj1",
                **result
            )
        )
    mid_n1 = time.perf_counter()
    db.commit()
    end_n1 = time.perf_counter()

    time_n1_add = mid_n1 - start_n1
    time_n1_commit = end_n1 - mid_n1
    time_n1_total = end_n1 - start_n1

    print(f"N+1 Approach:")
    print(f"  Add time:    {time_n1_add:.4f}s")
    print(f"  Commit time: {time_n1_commit:.4f}s")
    print(f"  Total time:  {time_n1_total:.4f}s")

    # Clean up
    db.query(ValidationRecord).delete()
    db.commit()

    # 2. add_all approach
    start_bulk = time.perf_counter()
    records = []
    for result in results:
        records.append(
            ValidationRecord(
                organization_id="org1",
                analysis_run_id="run1",
                project_id="proj1",
                **result
            )
        )
    mid_bulk_1 = time.perf_counter()
    db.add_all(records)
    mid_bulk_2 = time.perf_counter()
    db.commit()
    end_bulk = time.perf_counter()

    time_bulk_create = mid_bulk_1 - start_bulk
    time_bulk_add = mid_bulk_2 - mid_bulk_1
    time_bulk_commit = end_bulk - mid_bulk_2
    time_bulk_total = end_bulk - start_bulk

    print(f"\nadd_all Approach:")
    print(f"  Create objects time: {time_bulk_create:.4f}s")
    print(f"  add_all time:        {time_bulk_add:.4f}s")
    print(f"  Commit time:         {time_bulk_commit:.4f}s")
    print(f"  Total time:          {time_bulk_total:.4f}s")

    print(f"\nImprovement: {(time_n1_total - time_bulk_total) / time_n1_total * 100:.2f}% faster")

if __name__ == "__main__":
    run_test()
