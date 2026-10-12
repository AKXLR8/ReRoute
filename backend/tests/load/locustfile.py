"""Locust load test for ReRouteAI.

Run:
    locust -f tests/load/locustfile.py --host http://localhost:8000

Web UI at http://localhost:8089
"""

from locust import HttpUser, between, task

API_KEY = "change-me-admin-key"


class GatewayUser(HttpUser):
    """Simulates a client hitting the gateway."""

    wait_time = between(0.5, 2.0)
    host = "http://localhost:8000"

    def on_start(self):
        self.headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json",
        }

    @task(10)
    def chat_completion(self):
        self.client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "Say hello"}],
                "max_tokens": 10,
            },
            headers=self.headers,
            name="/v1/chat/completions [gpt-4o-mini]",
        )

    @task(5)
    def list_models(self):
        self.client.get("/v1/models", headers=self.headers, name="/v1/models")

    @task(3)
    def health(self):
        self.client.get("/health", name="/health")

    @task(2)
    def metrics(self):
        self.client.get("/metrics", name="/metrics")

    @task(1)
    def list_teams(self):
        self.client.get("/admin/teams", headers=self.headers, name="/admin/teams")

    @task(1)
    def analytics(self):
        self.client.get("/admin/analytics?days=1", headers=self.headers, name="/admin/analytics")
