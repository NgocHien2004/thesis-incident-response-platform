import requests
import json
import os

# ATT&CK Enterprise v14.1 — STIX format
URL = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
OUTPUT = "data/attck_enterprise.json"

os.makedirs("data", exist_ok=True)

print("Đang tải ATT&CK data...")
response = requests.get(URL, timeout=60)
data = response.json()

# Lưu toàn bộ
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)

# Đếm số technique
techniques = [
    obj for obj in data["objects"]
    if obj.get("type") == "attack-pattern"
    and not obj.get("revoked", False)
    and not obj.get("x_mitre_deprecated", False)
]

print(f"Tải xong! {len(techniques)} techniques")
print(f"ATT&CK version: {data.get('spec_version')}")
print(f"Lưu tại: {OUTPUT}")