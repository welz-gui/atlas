import time
from datetime import datetime

class MFARecoveryCode:
    def __init__(self, code_hash):
        self.used_at = None
        self.code_hash = code_hash

class User:
    def __init__(self):
        self.recovery_codes = []
        self.mfa_secret = None

class MockDB:
    def commit(self):
        time.sleep(0.01) # simulate db latency

def verify_recovery_code(code, code_hash):
    return True

def consume_second_factor_old(db, user, code):
    for recovery in user.recovery_codes:
        if recovery.used_at is None and verify_recovery_code(
            code, recovery.code_hash
        ):
            recovery.used_at = datetime.utcnow()
            db.commit()
            return True
    return False

def consume_second_factor_new(db, user, code):
    found = False
    for recovery in user.recovery_codes:
        if recovery.used_at is None and verify_recovery_code(
            code, recovery.code_hash
        ):
            recovery.used_at = datetime.utcnow()
            found = True
            break

    if found:
        db.commit()
        return True
    return False

# Setup
user_old = User()
user_old.recovery_codes = [MFARecoveryCode(f"hash_{i}") for i in range(10)]
user_new = User()
user_new.recovery_codes = [MFARecoveryCode(f"hash_{i}") for i in range(10)]
db = MockDB()

start = time.time()
for _ in range(10):
    consume_second_factor_old(db, user_old, "code")
print("Old:", time.time() - start)

start = time.time()
for _ in range(10):
    consume_second_factor_new(db, user_new, "code")
print("New:", time.time() - start)
