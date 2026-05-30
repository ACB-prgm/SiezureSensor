def test_status_endpoint_returns_database_summary(client):
  response = client.get("/api/v1/status")

  assert response.status_code == 200
  body = response.json()
  assert body["status"] == "ok"
  assert body["session_count"] == 0
  assert body["batch_count"] == 0
  assert body["sample_count"] == 0
  assert body["latest_session"] is None
