def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "TechQuery API" in data["message"]

def test_health_check_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["database"]["status"] == "connected"
    assert "gemini" in data

def test_supported_subjects(client):
    response = client.get("/api/v1/subjects")
    assert response.status_code == 200
    subjects = response.json()
    assert isinstance(subjects, list)
    assert subjects == ["All", "C", "C++", "Java", "Python"]
