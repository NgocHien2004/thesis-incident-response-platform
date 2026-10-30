import sys

import requests

BASE = "http://localhost:8000"
USER, PASSWORD = "analyst01", "Test@1234"


def main():
    r = requests.post(f"{BASE}/auth/login", json={"username": USER, "password": PASSWORD})
    r.raise_for_status()
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    alerts = requests.get(f"{BASE}/alerts/", headers=headers).json()
    todo = [a for a in alerts if a.get("ml_zone") is None]
    print(f"{len(todo)}/{len(alerts)} cảnh báo chưa có điểm ưu tiên")

    done, failed = 0, 0
    for a in todo:
        res = requests.post(f"{BASE}/alerts/{a['id']}/score", headers=headers)
        if res.status_code == 200:
            done += 1
        else:
            failed += 1
            print(f"  lỗi #{a['id']}: {res.status_code} {res.text[:100]}")
    print(f"Đã chấm điểm {done}, lỗi {failed}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
