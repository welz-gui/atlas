import time
import os
import sys

# setup django or sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)

class MFARecoveryCode(Base):
    __tablename__ = 'mfa_recovery_codes'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    code_hash = Column(String(255))

engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# Insert user
u = User(id=1)
session.add(u)
session.commit()

# generate fake codes
codes = ["code_" + str(i) for i in range(1000)]

# N+1 Insert
start = time.perf_counter()
for c in codes:
    session.add(MFARecoveryCode(user_id=1, code_hash=c))
session.commit()
end = time.perf_counter()
print(f"N+1 add and commit (1000 items): {end - start:.5f} seconds")

# Clear
session.query(MFARecoveryCode).delete()
session.commit()

# add_all
start = time.perf_counter()
session.add_all([MFARecoveryCode(user_id=1, code_hash=c) for c in codes])
session.commit()
end = time.perf_counter()
print(f"add_all and commit (1000 items): {end - start:.5f} seconds")

# bulk_save_objects
session.query(MFARecoveryCode).delete()
session.commit()

start = time.perf_counter()
session.bulk_save_objects([MFARecoveryCode(user_id=1, code_hash=c) for c in codes])
session.commit()
end = time.perf_counter()
print(f"bulk_save_objects and commit (1000 items): {end - start:.5f} seconds")
