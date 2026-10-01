import requests
import time
import json

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