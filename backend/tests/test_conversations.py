def get_auth_token(client):
    register_payload = {
        "email": "coder@college.edu",
        "username": "CodeMaster",
        "password": "Password123!"
    }
    res = client.post("/api/v1/auth/register", json=register_payload)
    return res.json()["access_token"]

def test_conversations_flow(client):
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a conversation
    create_payload = {
        "title": "Java Interfaces Question",
        "subject": "Java"
    }
    res = client.post("/api/v1/conversations", json=create_payload, headers=headers)
    assert res.status_code == 201
    conv = res.json()
    conv_id = conv["id"]
    assert conv["title"] == "Java Interfaces Question"

    # 2. List conversations
    res_list = client.get("/api/v1/conversations", headers=headers)
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1

    # 3. Send message in conversation (when no Gemini key is set, returns informative message)
    msg_payload = {
        "question": "What is an interface in Java?",
        "subject": "Java",
        "explanation_level": "Beginner",
        "answer_style": "Detailed",
        "include_examples": True
    }
    res_msg = client.post(f"/api/v1/conversations/{conv_id}/messages", json=msg_payload, headers=headers)
    assert res_msg.status_code == 200
    msg_data = res_msg.json()
    assert "answer" in msg_data
    assert "sources" in msg_data

    # 4. Get conversation details (history)
    res_detail = client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert len(detail["messages"]) == 2  # 1 user + 1 assistant
    assert detail["messages"][0]["role"] == "user"
    assert detail["messages"][1]["role"] == "assistant"

    # 5. Delete conversation
    res_del = client.delete(f"/api/v1/conversations/{conv_id}", headers=headers)
    assert res_del.status_code == 200

    # 6. Verify deleted
    assert client.get(f"/api/v1/conversations/{conv_id}", headers=headers).status_code == 404
