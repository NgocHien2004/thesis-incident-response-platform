import argparse, csv, io, json, os, sys, time
import requests

BASE = "http://127.0.0.1:8000"
passed = failed = 0
results = []


def check(label, condition, note=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ PASS | {label}" + (f" — {note}" if note else ""))
    else:
        failed += 1
        print(f"  ✗ FAIL | {label}" + (f" — {note}" if note else ""))
    results.append({"test": label, "pass": bool(condition), "note": note})


class Api:
    def __init__(self):
        self.token = None

    def _h(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def call(self, method, path, **kw):
        r = requests.request(method, BASE + path, headers=self._h(), timeout=120, **kw)
        try:
            body = r.json() if r.content else None
        except ValueError:
            body = None
        return r.status_code, body

    def get(self, path, **params):
        return self.call("GET", path, params=params)

    def post(self, path, payload=None):
        return self.call("POST", path, json=payload)

    def put(self, path, payload=None):
        return self.call("PUT", path, json=payload)

    def patch(self, path, payload=None):
        return self.call("PATCH", path, json=payload)

    def delete(self, path):
        return self.call("DELETE", path)

    def upload(self, incident_id, data_type, name, content):
        if isinstance(content, str):
            content = content.encode("utf-8")
        return self.call("POST", f"/incidents/{incident_id}/uploads", data={"data_type": data_type},
                         files={"file": (name, content, "application/octet-stream")})


def wait_upload(api, upload_id, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        _, up = api.get(f"/uploads/{upload_id}")
        if up and up["status"] in ("completed", "failed"):
            return up
        time.sleep(0.3)
    return up


def network_csv(features, kinds, extra_cols=False):
    # kinds: danh sách "ddos" / "scan" / "benign" / "crash"; một cột ".1" được ghi lại thành tên trùng như CIC-IDS2017
    header = [f[:-2] if f.endswith(".1") else f for f in features]
    if extra_cols:
        header += ["Label", "Timestamp"]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(header)
    for k in kinds:
        row = {f: "0" for f in features}
        if k == "ddos":
            row[" Flow Duration"], row[" Total Fwd Packets"] = "2000000", "10"
        elif k == "scan":
            row[" Flow Duration"], row[" Total Fwd Packets"] = "5000", "1"
        elif k == "benign":
            row[" Flow Duration"], row[" Total Fwd Packets"] = "5000", "10"
        elif k == "slow":
            row[" Flow Duration"], row[" Total Fwd Packets"] = "777777", "10"
        elif k == "crash":
            row[" Flow Duration"], row[" Total Fwd Packets"] = "123456789", "10"
        line = [row[f] for f in features]
        if extra_cols:
            line += ["DoS", "2017-07-05"]
        w.writerow(line)
    return out.getvalue()


def new_incident(api, title="Sự cố kiểm thử", **over):
    payload = {"title": title, "description": "Tạo bởi bộ kiểm thử", "attack_type": "ddos", "severity": "high",
               "occurred_at": "2026-11-01T08:30:00", "source": "ids_ips"}
    payload.update(over)
    return api.post("/incidents", payload)


def set_setting(api, key, value):
    return api.put(f"/settings/{key}", {"value": str(value)})


def run(args):
    global BASE
    BASE = args.base
    print("╔══════════════════════════════════════════════╗")
    print("║  KIỂM THỬ LUỒNG SỰ CỐ - UPLOAD - CẢNH BÁO   ║")
    print("╚══════════════════════════════════════════════╝")
    api = Api()

    print("\n── 1. Đăng nhập ──")
    s, _ = api.get("/incidents")
    check("Không có token thì bị từ chối", s in (401, 403), f"status={s}")
    s, _ = api.post("/auth/login", {"username": args.username, "password": "sai-mat-khau"})
    check("Sai mật khẩu trả 401", s == 401)
    s, body = api.post("/auth/login", {"username": args.username, "password": args.password})
    if s != 200:
        s2, _ = api.post("/auth/register", {"username": args.username, "password": args.password, "full_name": "Analyst Test"})
        s, body = api.post("/auth/login", {"username": args.username, "password": args.password})
    check("Đăng nhập thành công", s == 200 and body and "access_token" in body)
    if s != 200:
        print("Không đăng nhập được. Tạo tài khoản: python create_user.py <username> <password> \"<họ tên>\"")
        return False
    api.token = body["access_token"]
    s, me = api.get("/auth/me")
    check("/auth/me trả đúng người dùng", s == 200 and me["username"] == args.username and me["role"] == "analyst")

    print("\n── 2. Mô hình và cấu hình ──")
    s, models = api.post("/models/sync")
    check("Đồng bộ mô hình từ dịch vụ AI", s == 200 and any(m["task_type"] == "network" for m in models),
          f"status={s}")
    if s != 200:
        print("Dịch vụ AI chưa chạy: trong thư mục tests chạy uvicorn fake_ai_service:app --port 8001")
        return False
    net = next(m for m in models if m["task_type"] == "network")
    features = net["features"]
    check("Mô hình luồng mạng có danh sách cột đặc trưng", bool(features), f"{len(features)} cột")
    check("Có mô hình email đang hoạt động", any(m["task_type"] == "email" and m["is_active"] for m in models))
    s, st = api.get("/settings")
    keys = {x["key"] for x in st} if st else set()
    check("Có đủ khóa cấu hình", {"threshold_network", "threshold_email", "max_upload_mb", "max_rows", "batch_size"} <= keys)
    original = {x["key"]: x["value"] for x in st}
    s, _ = set_setting(api, "threshold_network", "1.5")
    check("Ngưỡng ngoài 0..1 bị từ chối", s == 422)
    s, _ = set_setting(api, "batch_size", "abc")
    check("Giá trị không phải số bị từ chối", s == 422)
    s, _ = set_setting(api, "khong_ton_tai", "1")
    check("Khóa cấu hình lạ bị từ chối", s in (404, 422))
    for k in ("threshold_network", "threshold_email"):
        set_setting(api, k, "0.8")
    set_setting(api, "batch_size", "500")
    s, labels = api.get("/labels", data_type="network")
    check("Danh sách nhãn có BENIGN không nguy hiểm", s == 200 and any(l["code"] == "BENIGN" and not l["is_dangerous"] for l in labels))

    print("\n── 3. Tạo, xem, sửa sự cố ──")
    s, inc = new_incident(api, "Sự cố DDoS thử nghiệm")
    check("Tạo sự cố thành công", s == 201, f"status={s}")
    inc_id = inc["id"]
    check("Trạng thái mặc định là Mới", inc["status"] == "new")
    check("Mã sự cố đúng dạng INC-năm-số", inc["code"].startswith("INC-") and inc["code"].count("-") == 2, inc["code"])
    s, other = new_incident(api, "Sự cố phishing thử nghiệm", attack_type="phishing", severity="medium", source="email")
    check("Mã sự cố không trùng nhau", other["code"] != inc["code"])
    s, _ = new_incident(api, severity="cuc_cao")
    check("Mức độ sai bị từ chối", s == 422)
    s, _ = new_incident(api, attack_type="khong_co")
    check("Loại tấn công không tồn tại bị từ chối", s == 422)
    s, _ = new_incident(api, source="facebook")
    check("Nguồn sai bị từ chối", s == 422)
    s, _ = new_incident(api, title="ab")
    check("Tiêu đề quá ngắn bị từ chối", s == 422)
    s, d = api.get(f"/incidents/{inc_id}")
    check("Trang chi tiết đúng dữ liệu", s == 200 and d["title"] == "Sự cố DDoS thử nghiệm" and d["attack_type"] == "ddos")
    check("Chi tiết cho biết có thể xóa khi chưa có cảnh báo", d["can_delete"] is True)
    s, u = api.put(f"/incidents/{inc_id}", {"title": "DDoS vào máy chủ web", "severity": "critical"})
    check("Sửa sự cố", s == 200 and u["title"] == "DDoS vào máy chủ web" and u["severity"] == "critical")
    s, _ = api.put(f"/incidents/{inc_id}", {"severity": "xyz"})
    check("Sửa với mức độ sai bị từ chối", s == 422)
    s, hist = api.get(f"/incidents/{inc_id}/history")
    check("Lịch sử có bản ghi tạo sự cố", s == 200 and len(hist) == 1 and hist[0]["new_status"] == "new")

    print("\n── 4. Danh sách, phân trang, sắp xếp, lọc ──")
    for i in range(5):
        new_incident(api, f"Sự cố phân trang {i}", attack_type="port_scan", severity="low")
    s, page = api.get("/incidents", page=1, page_size=3)
    check("Phân trang trả đúng cấu trúc", s == 200 and len(page["items"]) == 3 and page["total"] >= 7 and page["pages"] >= 3)
    s, p2 = api.get("/incidents", page=2, page_size=3)
    ids1, ids2 = {x["id"] for x in page["items"]}, {x["id"] for x in p2["items"]}
    check("Hai trang khác nhau không trùng bản ghi", not (ids1 & ids2))
    s, asc = api.get("/incidents", sort_by="id", order="asc", page_size=200)
    check("Sắp xếp tăng theo id", [x["id"] for x in asc["items"]] == sorted(x["id"] for x in asc["items"]))
    s, sev = api.get("/incidents", sort_by="severity", order="desc", page_size=200)
    rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    ranks = [rank[x["severity"]] for x in sev["items"]]
    check("Sắp xếp theo mức độ đúng thứ tự độ nghiêm trọng", ranks == sorted(ranks, reverse=True))
    s, r = api.get("/incidents", q=inc["code"])
    check("Tìm theo mã", s == 200 and any(x["id"] == inc_id for x in r["items"]))
    s, r = api.get("/incidents", q="phân trang")
    check("Tìm theo tiêu đề (có dấu)", s == 200 and r["total"] == 5)
    s, r = api.get("/incidents", attack_type="phishing")
    check("Lọc theo loại tấn công", s == 200 and r["items"] and all(x["attack_type"] == "phishing" for x in r["items"]))
    s, r = api.get("/incidents", status="new")
    check("Lọc theo trạng thái", s == 200 and all(x["status"] == "new" for x in r["items"]))
    s, r = api.get("/incidents", date_from="2026-11-01", date_to="2026-11-01")
    check("Lọc theo khoảng thời gian (gồm cả ngày cuối)", s == 200 and any(x["id"] == inc_id for x in r["items"]))
    s, r = api.get("/incidents", date_from="2026-12-01")
    check("Khoảng thời gian không có sự cố trả rỗng", s == 200 and not any(x["id"] == inc_id for x in r["items"]))
    s, _ = api.get("/incidents", sort_by="password_hash")
    check("Cột sắp xếp lạ bị từ chối", s == 422)

    print("\n── 5. Kiểm tra định dạng upload ──")
    good = network_csv(features, ["benign"] * 3)
    s, b = api.upload(inc_id, "network", "data.txt", good)
    check("Đuôi file lạ bị từ chối", s == 422)
    s, b = api.upload(inc_id, "video", "data.csv", good)
    check("Nguồn dữ liệu lạ bị từ chối", s == 422)
    s, b = api.upload(inc_id, "network", "empty.csv", "")
    check("File rỗng bị từ chối", s == 422)
    missing_cols = network_csv(features[:-3], ["benign"] * 3)
    s, b = api.upload(inc_id, "network", "thieu_cot.csv", missing_cols)
    check("Thiếu cột đặc trưng bị từ chối, báo rõ cột thiếu", s == 422 and "Thiếu" in str(b.get("detail")), str(b.get("detail"))[:90])
    bad_num = good.replace("5000", "abc", 1)
    s, b = api.upload(inc_id, "network", "sai_so.csv", bad_num)
    check("Ô không phải số bị từ chối, báo dòng và cột", s == 422 and "Dòng 1" in str(b.get("detail")), str(b.get("detail"))[:90])
    s, b = api.upload(inc_id, "network", "chi_header.csv", good.splitlines()[0] + "\n")
    check("File chỉ có tiêu đề bị từ chối", s == 422)
    s, b = api.upload(inc_id, "email", "email.csv", "subject,body\nA,B\n")
    check("Email thiếu cột sender/urls bị từ chối", s == 422 and "sender" in str(b.get("detail")))
    s, b = api.upload(inc_id, "email", "email.json", "{không phải json")
    check("JSON hỏng bị từ chối", s == 422)
    s, b = api.upload(inc_id, "email", "email.json", json.dumps({"x": 1}))
    check("JSON sai cấu trúc bị từ chối", s == 422)
    s, b = api.upload(inc_id, "network", "latin1.csv", good.encode("utf-8") + "\xe9".encode("latin-1"))
    check("File không phải UTF-8 bị từ chối", s == 422)
    set_setting(api, "max_upload_mb", "1")
    s, b = api.upload(inc_id, "network", "to.csv", "a" * 1_300_000)
    check("File quá kích thước bị từ chối (413)", s == 413)
    set_setting(api, "max_upload_mb", original.get("max_upload_mb", "50"))
    set_setting(api, "max_rows", "100")
    s, b = api.upload(inc_id, "network", "nhieu_dong.csv", network_csv(features, ["benign"] * 101))
    check("Quá số dòng cho phép bị từ chối", s == 422 and "100" in str(b.get("detail")))
    set_setting(api, "max_rows", original.get("max_rows", "100000"))
    s, d = api.get(f"/incidents/{inc_id}")
    check("Upload bị từ chối không để lại bản ghi", d["upload_count"] == 0)

    print("\n── 6. Upload luồng mạng, phân loại, sinh cảnh báo ──")
    kinds = ["ddos", "benign", "scan", "benign", "ddos", "benign", "ddos", "benign", "scan", "benign",
             "ddos", "benign", "ddos", "benign", "scan", "benign", "ddos", "benign", "scan", "benign"]
    ddos_rows = [i + 1 for i, k in enumerate(kinds) if k == "ddos"]
    content = network_csv(features, kinds, extra_cols=True)
    s, up = api.upload(inc_id, "network", "luong_mang.csv", content)
    check("Upload được nhận (202) và có trạng thái", s == 202 and up["status"] in ("pending", "processing", "completed"), f"status={s}")
    check("Lưu metadata file", up["original_filename"] == "luong_mang.csv" and up["file_size_bytes"] == len(content.encode("utf-8")) and len(up["file_hash"]) == 64)
    check("Đã đếm số dòng trước khi xử lý", up["row_count"] == 20)
    up = wait_upload(api, up["id"])
    check("Xử lý xong", up["status"] == "completed", up.get("error_message") or "")
    check("Đã xử lý đủ số dòng", up["processed_rows"] == 20)
    check("Phân bố nhãn đúng", up["label_distribution"] == {"DDoS": 6, "PortScan": 4, "BENIGN": 10}, str(up["label_distribution"]))
    check("Confidence trung bình hợp lý", up["avg_confidence"] is not None and 0.5 < up["avg_confidence"] < 1)
    check("Lưu phiên bản mô hình", up["model_version"] == "fake_v1" and up["model_id"] is not None)
    check("Lưu ngưỡng và lớp nguy hiểm đã áp dụng", up["threshold_used"] == 0.8 and "DDoS" in up["dangerous_labels_used"] and "BENIGN" not in up["dangerous_labels_used"])
    check("Chỉ mẫu vượt ngưỡng và thuộc lớp nguy hiểm sinh cảnh báo", up["alert_count"] == 6, f"alert_count={up['alert_count']}")
    s, al = api.get(f"/incidents/{inc_id}/alerts", page_size=100)
    check("Cảnh báo tự gắn vào sự cố", s == 200 and al["total"] == 6 and all(a["incident_id"] == inc_id and a["auto_linked"] for a in al["items"]))
    check("Chỉ số dòng truy vết đúng dòng gốc", sorted(a["row_index"] for a in al["items"]) == ddos_rows, str(sorted(a["row_index"] for a in al["items"])))
    check("Cảnh báo ghi file, nguồn, nhãn, confidence, thời gian", all(a["upload_filename"] == "luong_mang.csv" and a["source_type"] == "network" and a["predicted_label"] == "DDoS" and a["confidence"] >= 0.8 and a["created_at"] for a in al["items"]))
    check("Cảnh báo mới ở trạng thái chưa xác minh", all(a["verification_status"] == "unverified" for a in al["items"]))
    s, one = api.get(f"/alerts/{al['items'][0]['id']}")
    check("Chi tiết cảnh báo giữ nội dung dòng gốc", s == 200 and one["row_data"] and one["row_data"].get(" Flow Duration") == 2000000.0)

    print("\n── 7. Chống upload trùng ──")
    s, b = api.upload(inc_id, "network", "ten_khac.csv", content)
    check("Cùng nội dung trong cùng sự cố bị chặn (409)", s == 409, str(b.get("detail"))[:80])
    s, up_o = api.upload(other["id"], "network", "luong_mang.csv", content)
    check("Cùng file ở sự cố khác vẫn nhận nhưng cảnh báo", s == 202 and up_o["warnings"], str(up_o.get("warnings")))
    wait_upload(api, up_o["id"])

    print("\n── 8. Ngưỡng và lớp nguy hiểm cấu hình được ──")
    set_setting(api, "threshold_network", "0.5")
    s, i2 = new_incident(api, "Sự cố ngưỡng thấp")
    s, up2 = api.upload(i2["id"], "network", "n2.csv", network_csv(features, ["ddos"] * 3 + ["scan"] * 2 + ["benign"] * 5))
    up2 = wait_upload(api, up2["id"])
    check("Hạ ngưỡng xuống 0.5 thì PortScan cũng sinh cảnh báo", up2["alert_count"] == 5 and up2["threshold_used"] == 0.5, f"alert_count={up2['alert_count']}")
    set_setting(api, "threshold_network", "0.8")
    s, labs = api.get("/labels", data_type="network")
    scan_label = next(l for l in labs if l["code"] == "PortScan")
    api.put(f"/labels/{scan_label['id']}", {"is_dangerous": False})
    set_setting(api, "threshold_network", "0.5")
    s, up3 = api.upload(i2["id"], "network", "n3.csv", network_csv(features, ["ddos"] * 2 + ["scan"] * 4))
    up3 = wait_upload(api, up3["id"])
    check("Bỏ PortScan khỏi lớp nguy hiểm thì không sinh cảnh báo cho nó", up3["alert_count"] == 2 and "PortScan" not in up3["dangerous_labels_used"], f"alert_count={up3['alert_count']}")
    api.put(f"/labels/{scan_label['id']}", {"is_dangerous": True})
    set_setting(api, "threshold_network", "0.8")
    check("Đổi cấu hình không làm đổi cảnh báo của file đã xử lý", api.get(f"/uploads/{up2['id']}")[1]["alert_count"] == 5)

    print("\n── 9. Upload thất bại thì không sinh cảnh báo (nguyên tử) ──")
    set_setting(api, "batch_size", "10")
    s, i3 = new_incident(api, "Sự cố lỗi xử lý")
    bad = network_csv(features, ["ddos"] * 25 + ["crash"] + ["ddos"] * 4)
    s, upb = api.upload(i3["id"], "network", "loi.csv", bad)
    upb = wait_upload(api, upb["id"])
    check("File gặp lỗi giữa chừng có trạng thái Lỗi", upb["status"] == "failed" and upb["error_message"], str(upb.get("error_message"))[:80])
    s, al = api.get(f"/incidents/{i3['id']}/alerts")
    check("Không có cảnh báo nào được ghi dù các lô trước đã chạy xong", al["total"] == 0)
    check("Vẫn có tiến độ của các lô đã chạy", 0 < upb["processed_rows"] < 30, f"processed_rows={upb['processed_rows']}")
    s, again = api.upload(i3["id"], "network", "loi.csv", bad)
    check("Upload lại đúng file đã lỗi không bị coi là trùng", s == 202, f"status={s}")
    wait_upload(api, again["id"])
    fixed = network_csv(features, ["ddos"] * 30)
    s, upf = api.upload(i3["id"], "network", "da_sua.csv", fixed)
    upf = wait_upload(api, upf["id"])
    check("File đã sửa xử lý xong, theo nhiều lô", upf["status"] == "completed" and upf["alert_count"] == 30 and upf["processed_rows"] == 30)
    set_setting(api, "batch_size", "500")
    s, d = api.get(f"/incidents/{i3['id']}")
    check("Sự cố đã có cảnh báo thì chi tiết báo không xóa được", d["can_delete"] is False)

    print("\n── 10. Upload email ──")
    emails = [
        {"subject": "Free money now", "body": "Claim your FREE MONEY today", "sender": "a@x.com", "urls": "http://a.com http://b.com"},
        {"subject": "Họp tuần", "body": "Lịch họp thứ hai", "sender": "boss@corp.vn", "urls": ""},
        {"subject": "Verify", "body": "Please verify your account", "sender": "b@y.com", "urls": ["http://p.com"]},
        {"subject": "Nhiều link", "body": "xem", "sender": "c@z.com", "urls": "http://1.com,http://2.com;http://3.com"},
    ]
    s, i4 = new_incident(api, "Sự cố email", attack_type="phishing", source="email")
    s, upe = api.upload(i4["id"], "email", "mail.json", json.dumps(emails, ensure_ascii=False))
    check("Upload JSON email được nhận", s == 202, str(upe)[:100])
    upe = wait_upload(api, upe["id"])
    check("Phân bố nhãn email đúng", upe["label_distribution"] == {"SPAM": 3, "NON_SPAM": 1}, str(upe["label_distribution"]))
    check("Chỉ thư SPAM đủ ngưỡng 0.8 sinh cảnh báo", upe["alert_count"] == 2, f"alert_count={upe['alert_count']}")
    s, al = api.get(f"/incidents/{i4['id']}/alerts", source_type="email")
    check("Cảnh báo email truy vết đúng dòng", sorted(a["row_index"] for a in al["items"]) == [1, 3])
    s, one = api.get(f"/alerts/{al['items'][0]['id']}")
    check("Lưu subject, sender, urls của thư", one["row_data"]["sender"] and "subject" in one["row_data"] and isinstance(one["row_data"]["urls"], list))
    csv_mail = "subject,body,sender,urls\n\"Free money\",\"free money inside\",x@y.com,http://a.com\n"
    s, upc = api.upload(i4["id"], "email", "mail.csv", csv_mail)
    upc = wait_upload(api, upc["id"])
    check("Upload CSV email cũng chạy", upc["status"] == "completed" and upc["alert_count"] == 1)
    s, ups = api.get(f"/incidents/{i4['id']}/uploads")
    check("Danh sách file của sự cố", s == 200 and len(ups) == 2)

    print("\n── 11. Xem, lọc, sắp xếp cảnh báo ──")
    s, big = new_incident(api, "Sự cố nhiều cảnh báo")
    big_id = big["id"]
    s, upg = api.upload(big_id, "network", "lon.csv", network_csv(features, ["ddos"] * 125 + ["scan"] * 5))
    upg = wait_upload(api, upg["id"])
    check("125 cảnh báo sinh ra từ một file", upg["alert_count"] == 125, f"alert_count={upg['alert_count']}")
    s, pg = api.get(f"/incidents/{big_id}/alerts", page=1, page_size=50)
    check("Phân trang cảnh báo", len(pg["items"]) == 50 and pg["total"] == 125 and pg["pages"] == 3)
    s, srt = api.get(f"/incidents/{big_id}/alerts", sort_by="confidence", order="desc", page_size=500)
    confs = [a["confidence"] for a in srt["items"]]
    check("Sắp xếp cảnh báo theo confidence giảm dần", confs == sorted(confs, reverse=True))
    s, f1 = api.get(f"/incidents/{big_id}/alerts", label="DDoS", page_size=500)
    check("Lọc theo nhãn", f1["total"] == 125)
    s, f2 = api.get(f"/incidents/{big_id}/alerts", label="BENIGN")
    check("Lọc nhãn không có cảnh báo trả rỗng", f2["total"] == 0)
    s, f3 = api.get(f"/incidents/{big_id}/alerts", source_type="email")
    check("Lọc theo nguồn", f3["total"] == 0)
    s, f4 = api.get(f"/incidents/{big_id}/alerts", verification_status="verified")
    check("Lọc theo trạng thái xác minh", f4["total"] == 0)
    s, _ = api.get(f"/incidents/{big_id}/alerts", verification_status="abc")
    check("Trạng thái xác minh lạ bị từ chối", s == 422)

    print("\n── 12. Xác minh cảnh báo (đơn lẻ và hàng loạt) ──")
    all_ids = [a["id"] for a in api.get(f"/incidents/{big_id}/alerts", page_size=500)[1]["items"]]
    s, v = api.patch(f"/alerts/{all_ids[0]}/verify", {"status": "verified", "note": "Đúng là DDoS"})
    check("Xác minh một cảnh báo", s == 200 and v["verification_status"] == "verified" and v["verified_by"] and v["verified_at"] and v["note"] == "Đúng là DDoS")
    s, _ = api.patch(f"/alerts/{all_ids[0]}/verify", {"status": "tuy_y"})
    check("Trạng thái xác minh sai bị từ chối", s == 422)
    s, r = api.post("/alerts/bulk-verify", {"alert_ids": all_ids[1:101], "status": "verified"})
    check("Xác minh hàng loạt 100 cảnh báo", s == 200 and r["updated"] == 100)
    s, r = api.post("/alerts/bulk-verify", {"alert_ids": all_ids[101:], "status": "dismissed", "note": "Máy quét nội bộ"})
    check("Bỏ qua hàng loạt 24 cảnh báo", s == 200 and r["updated"] == 24)
    s, d = api.get(f"/incidents/{big_id}")
    check("Đếm theo trạng thái xác minh ở chi tiết sự cố", (d["verified_alerts"], d["dismissed_alerts"], d["unverified_alerts"]) == (101, 24, 0), str((d["verified_alerts"], d["dismissed_alerts"], d["unverified_alerts"])))
    s, r = api.post("/alerts/bulk-verify", {"alert_ids": all_ids[:3] + [99999999], "status": "dismissed"})
    check("Có id không tồn tại thì không đổi gì (404)", s == 404)
    check("Cảnh báo không bị đổi sau lần lỗi", api.get(f"/alerts/{all_ids[0]}")[1]["verification_status"] == "verified")
    s, r = api.post("/alerts/bulk-verify", {"alert_ids": all_ids[:2], "status": "unverified"})
    check("Đặt lại về chưa xác minh", s == 200 and api.get(f"/alerts/{all_ids[0]}")[1]["verified_by"] is None)

    print("\n── 13. Gỡ và chuyển cảnh báo ──")
    mv = all_ids[:3]
    s, r = api.post("/alerts/move", {"alert_ids": mv, "to_incident_id": i2["id"], "reason": "Gắn nhầm sự cố"})
    check("Chuyển 3 cảnh báo sang sự cố khác", s == 200 and r["moved"] == 3)
    a = api.get(f"/alerts/{mv[0]}")[1]
    check("Cảnh báo đã thuộc sự cố mới, không còn tự động", a["incident_id"] == i2["id"] and a["auto_linked"] is False and a["linked_at"])
    check("Cảnh báo vẫn truy vết về file gốc", a["upload_id"] == upg["id"] and a["row_index"] >= 1)
    s, h = api.get(f"/alerts/{mv[0]}/moves")
    check("Lịch sử chuyển cảnh báo", s == 200 and len(h) == 1 and h[0]["from_incident_id"] == big_id and h[0]["to_incident_id"] == i2["id"] and h[0]["reason"] == "Gắn nhầm sự cố")
    s, _ = api.post("/alerts/move", {"alert_ids": mv, "to_incident_id": i2["id"]})
    check("Chuyển vào chính sự cố đang chứa bị từ chối", s == 409)
    s, r = api.post("/alerts/move", {"alert_ids": [mv[0]], "to_incident_id": None, "reason": "Không thuộc sự cố nào"})
    check("Gỡ cảnh báo khỏi sự cố", s == 200 and api.get(f"/alerts/{mv[0]}")[1]["incident_id"] is None)
    s, un = api.get("/alerts", unassigned="true", page_size=100)
    check("Cảnh báo bị gỡ nằm trong danh sách chưa gắn", s == 200 and any(x["id"] == mv[0] for x in un["items"]))
    s, r = api.patch(f"/alerts/{mv[0]}/verify", {"status": "verified"})
    check("Cảnh báo chưa gắn sự cố không xác minh được", s == 409)
    s, r = api.post("/alerts/bulk-verify", {"alert_ids": [mv[0], mv[1]], "status": "dismissed"})
    check("Xác minh hàng loạt có một cảnh báo không hợp lệ thì không đổi cảnh báo nào", s == 409 and api.get(f"/alerts/{mv[1]}")[1]["verification_status"] == "unverified")
    s, r = api.post("/alerts/move", {"alert_ids": [mv[0]], "to_incident_id": big_id})
    check("Gắn lại cảnh báo đã gỡ vào sự cố", s == 200 and api.get(f"/alerts/{mv[0]}")[1]["incident_id"] == big_id)
    s, h = api.get(f"/alerts/{mv[0]}/moves")
    check("Lịch sử ghi đủ ba lần (chuyển đi, gỡ, gắn lại)", len(h) == 3, f"{len(h)} bản ghi")
    s, d = api.get(f"/incidents/{big_id}")
    check("Số cảnh báo của sự cố cập nhật theo", d["alert_count"] == 123, f"alert_count={d['alert_count']}")
    check("Sự cố đã có cảnh báo thì không xóa được", api.delete(f"/incidents/{big_id}")[0] == 409)

    print("\n── 14. Dashboard ──")
    s, db = api.get("/dashboard")
    check("Dashboard tổng sự cố khớp tổng theo trạng thái", s == 200 and db["incidents_total"] == sum(db["incidents_by_status"].values()))
    check("Dashboard tổng cảnh báo khớp tổng theo nhãn", db["alerts_total"] == sum(x["count"] for x in db["alerts_by_label"]))
    ver = db["alerts_by_verification"]
    expect = round(ver["dismissed"] / (ver["verified"] + ver["dismissed"]), 4) if ver["verified"] + ver["dismissed"] else None
    check("Tỉ lệ bỏ qua = Bỏ qua / (Đã xác minh + Bỏ qua)", db["false_positive_rate"] == expect, f"{db['false_positive_rate']} vs {expect}")
    check("Dashboard có thống kê theo loại tấn công", any(x["code"] == "ddos" for x in db["incidents_by_attack_type"]))

    print("\n── 14b. File đang xử lý chặn đổi trạng thái ──")
    s, sl = new_incident(api, "Sự cố file chạy chậm")
    s, ups = api.upload(sl["id"], "network", "cham.csv", network_csv(features, ["slow"] * 3))
    s, d = api.get(f"/incidents/{sl['id']}")
    check("Đang xử lý file thì chi tiết báo số file đang chạy", d["processing_uploads"] == 1, f"processing_uploads={d['processing_uploads']}")
    check("Danh sách chuyển trạng thái bỏ Đã xử lý/Đã đóng/Hủy khi còn file chạy", d["allowed_transitions"] == ["in_progress"], str(d["allowed_transitions"]))
    api.patch(f"/incidents/{sl['id']}/status", {"new_status": "in_progress"})
    s, _ = api.patch(f"/incidents/{sl['id']}/status", {"new_status": "resolved"})
    check("Không chuyển sang Đã xử lý khi còn file đang chạy", s == 409)
    s, _ = api.patch(f"/incidents/{sl['id']}/status", {"new_status": "cancelled", "note": "thử hủy"})
    check("Không hủy khi còn file đang chạy", s == 409)
    check("Không xóa khi còn file đang chạy", api.delete(f"/incidents/{sl['id']}")[0] == 409)
    ups = wait_upload(api, ups["id"])
    check("File chạy chậm xong bình thường", ups["status"] == "completed")
    s, r = api.patch(f"/incidents/{sl['id']}/status", {"new_status": "resolved"})
    check("Xong file thì chuyển trạng thái được", s == 200)

    print("\n── 15. Chuyển trạng thái sự cố ──")
    s, _ = api.patch(f"/incidents/{inc_id}/status", {"new_status": "closed"})
    check("Không nhảy cóc từ Mới sang Đã đóng", s == 409)
    s, _ = api.patch(f"/incidents/{inc_id}/status", {"new_status": "tuy_y"})
    check("Trạng thái lạ bị từ chối", s == 422)
    s, r = api.patch(f"/incidents/{inc_id}/status", {"new_status": "in_progress"})
    check("Mới sang Đang xử lý", s == 200 and r["status"] == "in_progress")
    s, r = api.patch(f"/incidents/{inc_id}/status", {"new_status": "resolved"})
    check("Đang xử lý sang Đã xử lý, có mốc resolved_at", s == 200 and r["resolved_at"])
    s, up_r = api.upload(inc_id, "network", "muon.csv", network_csv(features, ["ddos"]))
    check("Không upload được khi sự cố đã xử lý", s == 409)
    s, _ = api.patch(f"/incidents/{inc_id}/status", {"new_status": "in_progress"})
    check("Mở lại sự cố bắt buộc có lý do", s == 422)
    s, r = api.patch(f"/incidents/{inc_id}/status", {"new_status": "in_progress", "note": "Phát hiện thêm luồng"})
    check("Mở lại có lý do thì được, xóa resolved_at", s == 200 and r["resolved_at"] is None)
    api.patch(f"/incidents/{inc_id}/status", {"new_status": "resolved"})
    s, r = api.patch(f"/incidents/{inc_id}/status", {"new_status": "closed"})
    check("Đã xử lý sang Đã đóng, có mốc closed_at", s == 200 and r["closed_at"])
    s, _ = api.patch(f"/incidents/{inc_id}/status", {"new_status": "in_progress", "note": "thử"})
    check("Đã đóng là trạng thái cuối", s == 409)
    s, _ = api.put(f"/incidents/{inc_id}", {"title": "Sửa sau khi đóng"})
    check("Sự cố đã đóng không sửa được", s == 409)
    closed_alert = api.get(f"/incidents/{inc_id}/alerts")[1]["items"][0]["id"]
    s, _ = api.patch(f"/alerts/{closed_alert}/verify", {"status": "verified"})
    check("Cảnh báo của sự cố đã đóng không xác minh được", s == 409)
    s, _ = api.post("/alerts/move", {"alert_ids": [closed_alert], "to_incident_id": i2["id"]})
    check("Cảnh báo của sự cố đã đóng không chuyển đi được", s == 409)
    s, _ = api.post("/alerts/move", {"alert_ids": [all_ids[5]], "to_incident_id": inc_id})
    check("Không chuyển cảnh báo vào sự cố đã đóng", s == 409)
    s, hist = api.get(f"/incidents/{inc_id}/history")
    seq = [(h["old_status"], h["new_status"]) for h in hist]
    check("Lịch sử chuyển trạng thái đủ và đúng thứ tự", seq == [(None, "new"), ("new", "in_progress"), ("in_progress", "resolved"), ("resolved", "in_progress"), ("in_progress", "resolved"), ("resolved", "closed")], str(seq))
    check("Lịch sử ghi người đổi và lý do", all(h["changed_by_name"] for h in hist) and any(h["note"] == "Phát hiện thêm luồng" for h in hist))

    print("\n── 16. Hủy và xóa sự cố ──")
    s, e1 = new_incident(api, "Sự cố tạo nhầm")
    s, r = api.patch(f"/incidents/{e1['id']}/status", {"new_status": "cancelled"})
    check("Hủy sự cố bắt buộc có lý do", s == 422)
    s, r = api.patch(f"/incidents/{e1['id']}/status", {"new_status": "cancelled", "note": "Tạo nhầm"})
    check("Hủy sự cố có lý do", s == 200 and r["status"] == "cancelled")
    s, e2 = new_incident(api, "Sự cố rỗng có file không ra cảnh báo")
    s, ue = api.upload(e2["id"], "network", "an_toan.csv", network_csv(features, ["benign"] * 4))
    ue = wait_upload(api, ue["id"])
    check("File toàn lưu lượng bình thường không sinh cảnh báo", ue["status"] == "completed" and ue["alert_count"] == 0)
    s, d = api.get(f"/incidents/{e2['id']}")
    check("Chưa có cảnh báo thì cho phép xóa", d["can_delete"] is True)
    check("Xóa sự cố chưa có cảnh báo", api.delete(f"/incidents/{e2['id']}")[0] == 204)
    check("Sự cố đã xóa không còn", api.get(f"/incidents/{e2['id']}")[0] == 404)
    check("File của sự cố đã xóa cũng mất", api.get(f"/uploads/{ue['id']}")[0] == 404)
    s, x = new_incident(api, "Sự cố có cảnh báo bị chuyển đi")
    s, ux = api.upload(x["id"], "network", "x.csv", network_csv(features, ["ddos"] * 2))
    ux = wait_upload(api, ux["id"])
    xs = [a["id"] for a in api.get(f"/incidents/{x['id']}/alerts")[1]["items"]]
    api.post("/alerts/move", {"alert_ids": xs, "to_incident_id": i4["id"], "reason": "Chuyển hết"})
    s, d = api.get(f"/incidents/{x['id']}")
    check("Chuyển hết cảnh báo đi thì sự cố gốc còn 0 cảnh báo", d["alert_count"] == 0)
    check("Nhưng vẫn không xóa được vì cảnh báo còn truy vết về file của nó", d["can_delete"] is False and api.delete(f"/incidents/{x['id']}")[0] == 409)

    for k, v in original.items():
        if k in ("threshold_network", "threshold_email", "max_upload_mb", "max_rows", "batch_size"):
            set_setting(api, k, v)

    print(f"\n{'=' * 50}")
    print(f"KẾT QUẢ: {passed} PASS / {failed} FAIL / {passed + failed} tổng")
    print(f"{'=' * 50}")
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "incident_alert_flow_results.json"), "w", encoding="utf-8") as f:
        json.dump({"passed": passed, "failed": failed, "total": passed + failed,
                   "pass_rate_pct": round(passed / (passed + failed) * 100, 1), "details": results},
                  f, indent=2, ensure_ascii=False)
    print("Kết quả lưu tại tests/results/incident_alert_flow_results.json")
    return failed == 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--username", default="analyst01")
    ap.add_argument("--password", default="Test@1234")
    sys.exit(0 if run(ap.parse_args()) else 1)
