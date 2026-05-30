def test_workbench_origin_is_allowed(client):
  response = client.options(
    "/api/v1/sessions",
    headers={
      "Origin": "http://127.0.0.1:5173",
      "Access-Control-Request-Method": "GET",
    },
  )

  assert response.status_code == 200
  assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
