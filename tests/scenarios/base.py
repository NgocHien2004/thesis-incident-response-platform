import requests
import time
import json
import uuid

BASE_URL = "http://localhost:8000"

class ScenarioRunner:
    def __init__(self, username: str, password: str):
        self.base_url = BASE_URL
        self.token    = None
        self.username = username
        self.password = password
        self.timings  = {}

    def login(self):
        resp = requests.post(f"{self.base_url}/auth/login", json={
            "username": self.username,
            "password": self.password
        })
        resp.raise_for_status()
        self.token = resp.json()["access_token"]
        return self

    def headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def post(self, path, payload):
        resp = requests.post(
            f"{self.base_url}{path}",
            json=payload,
            headers=self.headers()
        )
        if not resp.ok:
            print(f"  ERROR {resp.status_code}: {resp.text[:200]}")
            return None
        return resp.json()

    def patch(self, path, payload=None):
        resp = requests.patch(
            f"{self.base_url}{path}",
            json=payload or {},
            headers=self.headers()
        )
        if not resp.ok:
            print(f"  ERROR {resp.status_code}: {resp.text[:200]}")
            return None
        return resp.json()

    def get(self, path):
        resp = requests.get(
            f"{self.base_url}{path}",
            headers=self.headers()
        )
        if not resp.ok:
            return None
        return resp.json()

    def tick(self, label):
        self.timings[label] = time.time()

    def elapsed(self, from_label, to_label):
        if from_label in self.timings and to_label in self.timings:
            return round(self.timings[to_label] - self.timings[from_label], 2)
        return None

    def raw(self, method, path, payload=None):
        return requests.request(
            method, f"{self.base_url}{path}",
            json=payload, headers=self.headers()
        )


PASSWORD = "Test@1234"


def login_all():
    return {
        "analyst":  ScenarioRunner("analyst01",     PASSWORD).login(),
        "analyst2": ScenarioRunner("analyst02",     PASSWORD).login(),
        "it":       ScenarioRunner("it01",          PASSWORD).login(),
        "st":       ScenarioRunner("stakeholder01", PASSWORD).login(),
        "au":       ScenarioRunner("auditor01",     PASSWORD).login(),
    }


def new_incident(u, title="Incident kiểm thử", investigating=True, asset_id=None):
    """Tạo asset (nếu cần) + alert đã triage + incident; commander mặc định là analyst01."""
    if asset_id is None:
        asset_id = u["it"].raw("POST", "/assets/", {
            "name": f"Tài sản {title}", "asset_type": "server", "criticality": "medium"
        }).json()["id"]
    alert = u["it"].raw("POST", "/alerts/", {
        "title": f"Cảnh báo {title}", "source": "manual", "severity": "high",
        "ioc": f"ioc-{uuid.uuid4().hex[:8]}.example.com", "affected_asset": asset_id
    }).json()
    u["it"].raw("PATCH", f"/alerts/{alert['id']}/triage", {
        "triage_type": "test", "triage_severity": "high",
        "triage_confidence": 80, "triage_sla_hours": 8
    })
    inc = u["analyst"].raw("POST", "/incidents/", {
        "title": title, "severity": "high", "alert_ids": [alert["id"]]
    }).json()
    if investigating:
        u["analyst"].raw("PATCH", f"/incidents/{inc['id']}/status", {"status": "investigating"})
    return inc["id"]

