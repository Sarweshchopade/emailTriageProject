from fastapi.testclient import TestClient

from server.app import app


def test_root_serves_custom_ui():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Email Triage Studio" in response.text


def test_ui_session_lifecycle():
    client = TestClient(app)

    create_response = client.post("/ui/session", json={"task_name": "easy"})
    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["task_name"] == "easy"
    assert payload["recommended_action"] is not None

    session_id = payload["session_id"]
    email_id = payload["current_emails"][0]["id"]

    action_response = client.post(
        f"/ui/session/{session_id}/action",
        json={
            "action": {
                "action_type": "classify",
                "email_id": email_id,
                "priority": payload["current_emails"][0]["priority_hint"],
            }
        },
    )

    assert action_response.status_code == 200
    action_payload = action_response.json()
    assert action_payload["session_id"] == session_id
    assert "last_reward" in action_payload
