def test_register_and_login_flow(client):
    # 1. Register new user
    register_payload = {
        "email": "student@college.edu",
        "username": "StudentUser",
        "password": "Password123!"
    }
    res = client.post("/api/v1/auth/register", json=register_payload)
    assert res.status_code == 201
    reg_data = res.json()
    assert "access_token" in reg_data
    token = reg_data["access_token"]
    assert reg_data["user"]["email"] == "student@college.edu"

    # 2. Cannot register with duplicate email
    res_dup = client.post("/api/v1/auth/register", json=register_payload)
    assert res_dup.status_code == 400

    # 3. Login with registered user
    login_payload = {
        "email": "student@college.edu",
        "password": "Password123!"
    }
    res_login = client.post("/api/v1/auth/login", json=login_payload)
    assert res_login.status_code == 200
    login_data = res_login.json()
    assert "access_token" in login_data

    # 4. Wrong password returns 401
    bad_login = {
        "email": "student@college.edu",
        "password": "WrongPassword!"
    }
    assert client.post("/api/v1/auth/login", json=bad_login).status_code == 401

    # 5. Get current user profile
    headers = {"Authorization": f"Bearer {token}"}
    res_me = client.get("/api/v1/auth/me", headers=headers)
    assert res_me.status_code == 200
    me_data = res_me.json()
    assert me_data["username"] == "StudentUser"

    # 6. Preferences default and update
    res_pref = client.get("/api/v1/users/preferences", headers=headers)
    assert res_pref.status_code == 200
    pref_data = res_pref.json()
    assert pref_data["explanation_level"] == "Intermediate"

    update_pref = {
        "explanation_level": "Beginner",
        "answer_style": "Concise",
        "include_examples": False,
        "preferred_subject": "Java"
    }
    res_update = client.put("/api/v1/users/preferences", json=update_pref, headers=headers)
    assert res_update.status_code == 200
    assert res_update.json()["explanation_level"] == "Beginner"
    assert res_update.json()["include_examples"] is False
