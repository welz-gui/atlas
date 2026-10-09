import pytest
from app.main import app

def test_login_rate_limit(client):
    from app.core.limiter import limiter
    limiter.enabled = True

    email = "test@atlas-qa.com"
    password = "password"

    # Send 5 requests to login
    for i in range(5):
        client.post("/api/v1/auth/login", json={"email": email, "password": password})

    # 6th request should fail
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 429
