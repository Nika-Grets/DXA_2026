from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

app = create_app(Settings())

with TestClient(app) as client:
    print("health:", client.get("/health").status_code)
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "debug@example.com",
            "full_name": "Debug Doctor",
            "password": "correct-horse-battery-staple",
        },
    )
    print("register:", r.status_code)
    print(r.text)
