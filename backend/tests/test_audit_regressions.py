def test_abstention_has_no_follow_up_prompts(client):
    response = client.post('/api/v1/query', json={'question': 'What is the orbital period of Neptune?', 'subject': 'Java'})
    assert response.status_code == 200
    assert response.json()['abstained'] is True
    assert response.json()['suggested_questions'] == []


def test_validation_does_not_echo_input_or_credentials(client):
    supplied = 'private question ' * 400
    response = client.post('/api/v1/query', json={'question': supplied})
    assert response.status_code == 422
    assert supplied not in response.text
    for error in response.json()['detail']:
        assert 'input' not in error and 'ctx' not in error
    password = 'confidential-password-should-not-be-reflected'
    response = client.post('/api/v1/auth/register', json={'email': 'not-an-email', 'username': 'x', 'password': password})
    assert response.status_code == 422
    assert password not in response.text


def test_registration_normalizes_email_and_enforces_password_byte_limit(client):
    body = {'email': 'Person@example.com', 'username': ' Person ', 'password': 'Password123!'}
    first = client.post('/api/v1/auth/register', json=body)
    assert first.status_code == 201 and first.json()['user']['username'] == 'Person'
    body['email'] = 'PERSON@example.com'
    assert client.post('/api/v1/auth/register', json=body).status_code == 400
    body['email'] = 'second@example.com'
    body['password'] = '\U0001f600' * 20
    response = client.post('/api/v1/auth/register', json=body)
    assert response.status_code == 422 and 'input' not in response.json()['detail'][0]


def test_conversation_history_preserves_modes_and_no_abstention_suggestions(client):
    account = client.post('/api/v1/auth/register', json={'email': 'history@example.com', 'username': 'History', 'password': 'Password123!'})
    headers = {'Authorization': 'Bearer ' + account.json()['access_token']}
    conv = client.post('/api/v1/conversations', json={'title': 'Audit'}, headers=headers).json()
    response = client.post(f"/api/v1/conversations/{conv['id']}/messages", headers=headers, json={'question': 'What is the orbital period of Neptune?'})
    assert response.json()['suggested_questions'] == []
    history = client.get(f"/api/v1/conversations/{conv['id']}", headers=headers).json()['messages'][-1]
    assert history['abstained'] is True and history['response_mode'] == 'abstained'
    assert history['retrieval_mode'] == 'none' and history['suggested_questions'] == []
