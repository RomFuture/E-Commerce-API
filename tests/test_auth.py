def test_signup_login_me(client):
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": "user@test.com", "password": "password12"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "user@test.com"

    r2 = client.post(
        "/api/v1/auth/login",
        data={"username": "user@test.com", "password": "password12"},
    )
    assert r2.status_code == 200
    token = r2.json()["access_token"]

    r3 = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r3.status_code == 200
    assert r3.json()["email"] == "user@test.com"


def test_signup_duplicate(client):
    body = {"email": "dup@test.com", "password": "password12"}
    assert client.post("/api/v1/auth/signup", json=body).status_code == 201
    r = client.post("/api/v1/auth/signup", json=body)
    assert r.status_code == 409


def test_admin_endpoint(client):
    client.post(
        "/api/v1/auth/signup",
        json={"email": "admin@test.com", "password": "password12"},
    )
    token = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.com", "password": "password12"},
    ).json()["access_token"]
    ok = client.get(
        "/api/v1/admin/health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok.status_code == 200
    assert ok.json() == {"admin": True}

    client.post(
        "/api/v1/auth/signup",
        json={"email": "user2@test.com", "password": "password12"},
    )
    user_token = client.post(
        "/api/v1/auth/login",
        data={"username": "user2@test.com", "password": "password12"},
    ).json()["access_token"]
    forbidden = client.get(
        "/api/v1/admin/health",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert forbidden.status_code == 403
