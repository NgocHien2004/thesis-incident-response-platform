import sys, os, json, uuid
import requests
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
from app.services import scoring_rules as sr
from tests.scenarios.base import login_all, BASE_URL as BASE

passed = 0
failed = 0
skipped = 0
results = []
BLOCK = (401, 403)


def expect(label, resp, *codes):
    global passed, failed
    ok = resp.status_code in codes
    passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
    note = "" if ok else f" (nhận {resp.status_code}: {resp.text[:110]})"
    results.append({"test": label, "expected": list(codes), "actual": resp.status_code, "pass": ok})
    print(f"  {'✓ PASS' if ok else '✗ FAIL'} | {label}{note}")
    return ok


def check(label, cond):
    global passed, failed
    passed, failed = (passed + 1, failed) if cond else (passed, failed + 1)
    results.append({"test": label, "expected": True, "actual": bool(cond), "pass": bool(cond)})
    print(f"  {'✓ PASS' if cond else '✗ FAIL'} | {label}")
    return cond


def skip(label, why):
    global skipped
    skipped += 1
    results.append({"test": label, "skipped": why})
    print(f"  – SKIP | {label} ({why})")


def zone_args(**kw):
    base = dict(p=0.05, p_source="rf", priority=5.0, asset_criticality="low", asset_w=0.25, source="ids_ips",
                declared_severity="low", group_has_open_risk=False)
    base.update(kw)
    return base


def unit_tests():
    print("\n── 1. Công thức điểm ưu tiên ──")
    check("Xác suất 1, tài sản và nguồn tối đa cho 100 điểm", sr.priority_score(1.0, 1.0, 1.0) == 100.0)
    check("Điểm ưu tiên khớp công thức (1; 0,25; 0,5 cho 67,5)", sr.priority_score(1.0, 0.25, 0.5) == 67.5)
    check("Điểm ưu tiên khớp công thức (0,5; 0,5; 0,8 cho 40,5)", sr.priority_score(0.5, 0.5, 0.8) == 40.5)
    check("Xác suất 0 cho điểm 0 dù tài sản quan trọng", sr.priority_score(0.0, 1.0, 1.0) == 0.0)
    check("Điểm tăng theo mức quan trọng của tài sản",
          sr.priority_score(0.6, 0.25, 0.7) < sr.priority_score(0.6, 0.5, 0.7) < sr.priority_score(0.6, 1.0, 0.7))
    check("Điểm tăng theo độ tin cậy của nguồn", sr.priority_score(0.6, 0.5, 0.5) < sr.priority_score(0.6, 0.5, 0.9))
    check("Điểm tăng theo xác suất", sr.priority_score(0.2, 0.5, 0.7) < sr.priority_score(0.9, 0.5, 0.7))
    check("Điểm luôn nằm trong khoảng 0 đến 100",
          all(0 <= sr.priority_score(p / 10, a, s) <= 100 for p in range(0, 11) for a in (0.25, 1.0) for s in (0.0, 1.0)))
    check("Tài sản không rõ tính như mức trung bình", sr.asset_weight(None) == sr.asset_weight("medium"))

    print("\n── 2. Chia ba vùng ──")
    z = sr.decide_zone(**zone_args())
    check("Đạt mọi luật an toàn thì đề xuất tự đóng", z[0] == "auto_close")
    for label, kw in (
        ("xác suất không do mô hình ML tính", dict(p_source="declared_severity")),
        ("xác suất từ 0,15 trở lên", dict(p=0.15, priority=15.0)),
        ("tài sản quan trọng mức cao", dict(asset_criticality="high", asset_w=0.75)),
        ("không có tài sản", dict(asset_criticality=None, asset_w=0.5)),
        ("mức độ khai báo là cao", dict(declared_severity="high")),
        ("báo cáo thủ công của con người", dict(source="manual")),
        ("nhóm cảnh báo có alert đang cần xem", dict(group_has_open_risk=True)),
    ):
        zone = sr.decide_zone(**zone_args(**kw))[0]
        check(f"Không tự đóng khi {label}", zone == "review")
    check("Điểm từ 65 là khẩn", sr.decide_zone(**zone_args(p=1.0, priority=65.0, p_source="rf"))[0] == "urgent")
    check("Điểm dưới 65 không phải khẩn", sr.decide_zone(**zone_args(p=0.5, priority=64.9, p_source="rf",
                                                                     asset_criticality="medium", asset_w=0.5))[0] == "review")
    pr = sr.priority_score(0.8, 0.75, 0.0)
    check("Xác suất cao trên tài sản quan trọng là khẩn dù điểm dưới 65",
          pr < 65 and sr.decide_zone(**zone_args(p=0.8, priority=pr, asset_criticality="high", asset_w=0.75))[0] == "urgent")
    check("Xác suất cao trên tài sản thấp chưa tự thành khẩn khi điểm dưới 65",
          sr.decide_zone(**zone_args(p=0.8, priority=50.0, asset_criticality="low", asset_w=0.25))[0] == "review")
    zr = sr.decide_zone(**zone_args(p_source="declared_severity"))
    check("Kết quả có đủ luật đã kiểm tra và lý do", len(zr[2]) == 6 and bool(zr[1]))
    check("Xác suất suy từ mức độ khai báo không bao giờ tự đóng",
          all(sr.decide_zone(**zone_args(p=sr.declared_probability(sev), p_source="declared_severity",
                                         declared_severity=sev))[0] != "auto_close"
              for sev in ("info", "low", "medium", "high", "critical")))

    print("\n── 3. Đặc trưng luồng và cảnh báo tương tự ──")
    check("Đọc flow_features dạng object", sr.extract_flow_features(json.dumps({"flow_features": {"a": 1}})) == {"a": 1})
    check("Đọc flow_features dạng chuỗi JSON (cột CSV)",
          sr.extract_flow_features(json.dumps({"flow_features": json.dumps({"a": 2})})) == {"a": 2})
    check("Dữ liệu không phải JSON thì bỏ qua", sr.extract_flow_features("không phải json") is None)
    check("Không có flow_features thì bỏ qua", sr.extract_flow_features(json.dumps({"title": "x"})) is None)
    check("flow_features rỗng thì bỏ qua", sr.extract_flow_features(json.dumps({"flow_features": {}})) is None)
    pool = [(1, "SSH brute force attempts from 1.2.3.4"), (2, "Phishing email with attachment"), (3, "Port scan 10.0.0.9")]
    found = sr.rank_similar("Brute force SSH login from 1.2.3.4", pool)
    check("Tìm được cảnh báo tương tự và xếp đầu", found and found[0][0] == 1)
    check("Không trả về cảnh báo không liên quan", all(cid != 2 and cid != 3 for cid, _ in found))
    check("Danh sách ứng viên rỗng thì không có kết quả", sr.rank_similar("abc def", []) == [])
    check("Kết quả sắp xếp giảm dần theo độ tương tự",
          (lambda r: [x[1] for x in r] == sorted([x[1] for x in r], reverse=True))(
              sr.rank_similar("brute force ssh 1.2.3.4", [(1, "brute force ssh"), (2, "brute force ssh 1.2.3.4 login")])))


def consistent(alert):
    """Kiểm tra kết quả chấm điểm tự nhất quán với công thức, không phụ thuộc mô hình."""
    m = alert["ml_result"]
    comp = m["components"]
    pr = sr.priority_score(m["probability"], comp["asset"]["weight"], comp["source"]["reliability"])
    return (abs(pr - m["priority"]) < 0.11 and alert["ml_priority"] == int(round(m["priority"]))
            and alert["ml_zone"] == m["zone"])


def zone_ok(m):
    if m["priority"] >= sr.URGENT_PRIORITY:
        return m["zone"] == "urgent"
    if m["zone"] == "auto_close":
        return all(r["passed"] for r in m["rules"])
    if m["zone"] == "review":
        return not all(r["passed"] for r in m["rules"])
    return True


def api_tests():
    print("\n── 4. Chấm điểm khi nhập cảnh báo (qua API) ──")
    u = login_all()
    A, A2, IT, ST = u["analyst"], u["analyst2"], u["it"], u["st"]
    R = lambda who, m, p, body=None: who.raw(m, p, body)
    tag = uuid.uuid4().hex[:6]

    low = R(IT, "POST", "/assets/", {"name": f"Score low {tag}", "asset_type": "server", "criticality": "low",
                                     "hostname": f"score-low-{tag}", "ip_address": f"10.77.{int(tag[:2], 16)}.{int(tag[2:4], 16) % 250 + 1}"}).json()
    crit = R(IT, "POST", "/assets/", {"name": f"Score crit {tag}", "asset_type": "server", "criticality": "critical",
                                      "hostname": f"score-crit-{tag}"}).json()
    ioc = lambda: f"s-{uuid.uuid4().hex[:8]}.example.com"

    a = R(IT, "POST", "/alerts/", {"title": f"Có điểm {tag}", "source": "manual", "severity": "high", "ioc": ioc(),
                                   "affected_asset": crit["id"]}).json()
    check("Cảnh báo tạo mới đã được chấm điểm ngay", a.get("ml_zone") in ("urgent", "review") and a.get("ml_priority") is not None)
    m = a["ml_result"]
    check("Không có đặc trưng luồng thì xác suất suy từ mức độ khai báo", m["probability_source"] == "declared_severity")
    check("Kết quả chấm điểm khớp công thức và vùng", consistent(a) and zone_ok(m))
    check("Kết quả đánh dấu là nội dung do AI tạo và nêu tài sản, nguồn", m["ai_generated"] is True
          and m["components"]["asset"]["criticality"] == "critical" and m["components"]["source"]["name"] == "manual")
    check("Mức độ high trên tài sản critical là khẩn", a["ml_zone"] == "urgent")

    safe = R(IT, "POST", "/alerts/", {"title": f"Mức thấp {tag}", "source": "ids_ips", "severity": "info", "ioc": ioc(),
                                      "affected_asset": low["id"]}).json()
    check("Cảnh báo không có mô hình ML không bao giờ được đề xuất tự đóng", safe["ml_zone"] == "review")

    print("\n── 5. Nhập cảnh báo từ ngoài và gắn tài sản ──")
    w = R(IT, "POST", "/alerts/webhook", {"title": f"Webhook {tag}", "severity": "low", "ioc": ioc(),
                                          "asset_hostname": f"SCORE-LOW-{tag}"})
    expect("Webhook nhận cảnh báo kèm tên máy", w, 200)
    check("Webhook gắn đúng tài sản theo hostname (không phân biệt hoa thường)", w.json().get("affected_asset") == low["id"])
    w2 = R(IT, "POST", "/alerts/webhook", {"title": f"Webhook id {tag}", "severity": "low", "ioc": ioc(), "affected_asset": crit["id"]})
    check("Webhook gắn đúng tài sản theo id", w2.json().get("affected_asset") == crit["id"])
    w3 = R(IT, "POST", "/alerts/webhook", {"title": f"Webhook lạ {tag}", "severity": "low", "ioc": ioc(), "asset_hostname": "không-tồn-tại"})
    check("Tên máy không có trong danh sách thì không gắn tài sản", w3.json().get("affected_asset") is None)
    check("Tài sản không rõ tính như mức trung bình",
          w3.json()["ml_result"]["components"]["asset"]["weight"] == sr.asset_weight("medium"))

    print("\n── 5b. Trường source trong payload nhập từ ngoài ──")
    wh = lambda extra: R(IT, "POST", "/alerts/webhook", {"title": f"Nguồn {tag}", "severity": "low", "ioc": ioc(),
                                                         "affected_asset": low["id"], **extra})
    src_of = lambda resp: resp.json().get("source")
    rel_of = lambda resp: resp.json()["ml_result"]["components"]["source"]["reliability"]
    base_w = wh({})
    check("Webhook không có source thì dùng kênh nhập (webhook, S=0,7)", src_of(base_w) == "webhook" and rel_of(base_w) == sr.source_reliability("webhook"))
    ids_w = wh({"source": "ids_ips"})
    check("Webhook source=ids_ips được ghi nhận, S=0,8", src_of(ids_w) == "ids_ips" and rel_of(ids_w) == sr.source_reliability("ids_ips") == 0.8)
    check("Cùng tài sản và mức độ, nguồn ids_ips có điểm cao hơn webhook", ids_w.json()["ml_result"]["priority"] > base_w.json()["ml_result"]["priority"])
    check("Kết quả chấm điểm với nguồn khai báo vẫn khớp công thức", consistent(ids_w.json()) and zone_ok(ids_w.json()["ml_result"]))
    ep_w = wh({"source": "endpoint"})
    check("Webhook source=endpoint được ghi nhận, S=0,9", src_of(ep_w) == "endpoint" and rel_of(ep_w) == 0.9)
    em_w = wh({"source": "email"})
    check("Webhook source=email được ghi nhận, S=0,6 nên điểm thấp hơn webhook thường",
          src_of(em_w) == "email" and rel_of(em_w) == 0.6 and em_w.json()["ml_result"]["priority"] < base_w.json()["ml_result"]["priority"])
    check("source viết hoa và có khoảng trắng vẫn nhận", src_of(wh({"source": "  IDS_IPS "})) == "ids_ips")
    man_w = wh({"source": "manual"})
    check("source=manual bị bỏ qua (báo cáo thủ công chỉ tạo qua POST /alerts/)", src_of(man_w) == "webhook" and rel_of(man_w) == 0.7)
    check("source=csv_upload trong webhook bị bỏ qua", src_of(wh({"source": "csv_upload"})) == "webhook")
    for bad in ("không-hợp-lệ", "", None, 123, ["ids_ips"]):
        check(f"source không hợp lệ ({bad!r}) thì dùng kênh nhập", src_of(wh({"source": bad})) == "webhook")

    rows_in = [{"title": f"Dòng IDS {tag}", "severity": "low", "ioc": ioc(), "source": "ids_ips", "affected_asset": low["id"]},
               {"title": f"Dòng thủ công {tag}", "severity": "low", "ioc": ioc(), "source": "manual", "affected_asset": low["id"]},
               {"title": f"Dòng không nguồn {tag}", "severity": "low", "ioc": ioc(), "affected_asset": low["id"]},
               {"title": f"Dòng endpoint {tag}", "severity": "low", "ioc": ioc(), "source": "endpoint", "affected_asset": low["id"]}]
    want = ["ids_ips", "csv_upload", "csv_upload", "endpoint"]
    cols = ["title", "severity", "ioc", "source", "affected_asset"]
    csv_src = ",".join(cols) + "\n" + "\n".join(",".join(str(r.get(c, "")) for c in cols) for r in rows_in) + "\n"
    up = requests.post(f"{BASE}/alerts/upload/csv", headers=IT.headers(), files={"file": (f"src-{tag}.csv", csv_src.encode("utf-8"), "text/csv")})
    expect("Nhập CSV có cột source", up, 200)
    check("CSV: mỗi dòng nhận đúng nguồn (hợp lệ giữ, manual và để trống dùng csv_upload)",
          up.status_code == 200 and [a["source"] for a in up.json()] == want)
    upj = requests.post(f"{BASE}/alerts/upload/json", headers=IT.headers(),
                        files={"file": (f"src-{tag}.json", json.dumps(rows_in).encode("utf-8"), "application/json")})
    expect("Nhập JSON có trường source", upj, 200)
    check("JSON: mỗi phần tử nhận đúng nguồn", upj.status_code == 200 and [a["source"] for a in upj.json()] == want)

    print("\n── 6. Mô hình RF qua đặc trưng luồng mạng ──")
    sch = R(A, "GET", "/ai/classify/schema")
    if sch.status_code != 200:
        skip("Chấm điểm bằng mô hình RF", "AI service không chạy")
    else:
        names = sch.json()["features"]
        expect("Stakeholder xem danh sách đặc trưng", R(ST, "GET", "/ai/classify/schema"), 200)
        for label, val in (("toàn số 0", 0.0), ("giá trị lớn", 1e7)):
            feats = {n: val for n in names}
            r = R(IT, "POST", "/alerts/webhook", {"title": f"Luồng {label} {tag}", "severity": "low", "ioc": ioc(),
                                                  "flow_features": feats, "affected_asset": low["id"]})
            al = r.json()
            mm = al["ml_result"]
            check(f"Luồng {label}: xác suất do mô hình RF tính (0 đến 1)",
                  mm["probability_source"] == "rf" and 0.0 <= mm["probability"] <= 1.0 and not mm["ai_error"])
            check(f"Luồng {label}: điểm, vùng khớp công thức", consistent(al) and zone_ok(mm))
            check(f"Luồng {label}: có tối đa 5 đặc trưng nổi bật, mỗi cái có tên và điểm",
                  len(mm["top_features"]) <= 5 and all({"name", "value", "importance", "score"} <= set(f) for f in mm["top_features"]))
        csv_body = "title,severity,ioc,flow_features\n" + f'CSV luồng {tag},low,{ioc()},"{json.dumps({n: 0.0 for n in names}).replace(chr(34), chr(34) * 2)}"\n'
        up = requests.post(f"{BASE}/alerts/upload/csv", headers=IT.headers(),
                           files={"file": (f"flow-{tag}.csv", csv_body.encode("utf-8"), "text/csv")})
        expect("Nhập CSV có cột flow_features", up, 200)
        row = up.json()[0] if up.status_code == 200 else {}
        check("CSV: cột flow_features được mô hình RF chấm điểm",
              (row.get("ml_result") or {}).get("probability_source") == "rf")

    print("\n── 7. Phân quyền chấm lại, đóng và mở lại ──")
    expect("IT chấm lại điểm", R(IT, "POST", f"/alerts/{a['id']}/score"), 200)
    expect("Stakeholder chấm lại điểm bị chặn", R(ST, "POST", f"/alerts/{a['id']}/score"), *BLOCK)
    expect("Chấm điểm cảnh báo không tồn tại trả 404", R(A, "POST", "/alerts/999999/score"), 404)
    cl = lambda who, aid, note="Không cần xử lý": R(who, "PATCH", f"/alerts/{aid}/close", {"note": note})
    expect("IT đóng cảnh báo bị chặn", cl(IT, safe["id"]), *BLOCK)
    expect("Đóng cảnh báo không ghi lý do bị từ chối", cl(A, safe["id"], "  "), 400)
    r = cl(A, safe["id"])
    expect("Analyst đóng cảnh báo kèm lý do", r, 200)
    check("Cảnh báo đã đóng ở trạng thái closed", r.json().get("status") == "closed")
    expect("Đóng lại cảnh báo đã đóng bị từ chối", cl(A, safe["id"]), 400)
    ro = lambda who, aid, note="Cần xem lại": R(who, "PATCH", f"/alerts/{aid}/reopen", {"note": note})
    expect("IT mở lại cảnh báo bị chặn", ro(IT, safe["id"]), *BLOCK)
    expect("Mở lại không ghi lý do bị từ chối", ro(A, safe["id"], ""), 400)
    expect("Analyst mở lại cảnh báo đã đóng", ro(A, safe["id"]), 200)
    expect("Mở lại cảnh báo chưa đóng bị từ chối", ro(A, safe["id"]), 400)

    esc = R(IT, "POST", "/alerts/", {"title": f"Esc {tag}", "source": "ids_ips", "severity": "high", "ioc": ioc(), "affected_asset": crit["id"]}).json()
    R(IT, "PATCH", f"/alerts/{esc['id']}/triage", {"triage_type": "malware", "triage_severity": "high", "triage_confidence": 70, "triage_sla_hours": 8})
    R(A, "POST", "/incidents/", {"title": f"Esc {tag}", "severity": "high", "alert_ids": [esc["id"]]})
    expect("Đóng cảnh báo đã nâng thành incident bị từ chối", cl(A, esc["id"]), 400)

    print("\n── 8. Sắp xếp, lọc và cảnh báo tương tự ──")
    lst = R(A, "GET", "/alerts/?order=priority").json()
    pri = [x["ml_priority"] for x in lst if x.get("ml_priority") is not None]
    check("Sắp xếp theo điểm ưu tiên giảm dần", pri == sorted(pri, reverse=True) and len(pri) > 3)
    check("Cảnh báo chưa có điểm được xếp cuối", (lambda xs: xs == sorted(xs, key=lambda v: v is None))([x.get("ml_priority") for x in lst]))
    z = R(A, "GET", "/alerts/?zone=urgent").json()
    check("Lọc theo vùng khẩn chỉ trả về cảnh báo ở vùng đó", len(z) > 0 and all(x["ml_zone"] == "urgent" for x in z))

    base = f"Đăng nhập thất bại hàng loạt vào cổng VPN từ địa chỉ lạ {tag}"
    first = R(IT, "POST", "/alerts/", {"title": base, "description": "Hàng trăm lần đăng nhập sai liên tiếp", "source": "ids_ips",
                                       "severity": "medium", "ioc": ioc()}).json()
    second = R(IT, "POST", "/alerts/", {"title": base + " lần hai", "description": "Hàng trăm lần đăng nhập sai liên tiếp", "source": "ids_ips",
                                        "severity": "medium", "ioc": ioc()}).json()
    sims = second["ml_result"]["similar_alerts"]
    check("Cảnh báo gần giống được liệt kê là tương tự", any(s["id"] == first["id"] and s["similarity"] >= sr.SIMILAR_MIN for s in sims))
    check("Cảnh báo tương tự có đủ thông tin để mở", all({"id", "title", "similarity", "status"} <= set(s) for s in sims))

    print("\n── 9. Nhật ký kiểm toán ──")
    audit = R(A, "GET", "/audit/?entity_type=alert&limit=500")
    rows = audit.json() if audit.status_code == 200 else []
    rows = rows.get("items", rows) if isinstance(rows, dict) else rows
    actions = {x.get("action") for x in rows}
    check("Nhật ký ghi sự kiện chấm điểm cảnh báo", "alert.scored" in actions)
    check("Nhật ký ghi việc đóng cảnh báo", "alert.closed" in actions)
    v = R(A, "GET", "/audit/verify").json()
    check("Chuỗi băm nhật ký kiểm toán nguyên vẹn", v.get("ok") is True)


def run():
    print("╔══════════════════════════════════════════════╗")
    print("║  KIỂM THỬ CHẤM ĐIỂM VÀ ƯU TIÊN CẢNH BÁO      ║")
    print("╚══════════════════════════════════════════════╝")
    unit_tests()
    api_tests()
    print("\n" + "=" * 50)
    print(f"KẾT QUẢ: {passed}/{passed + failed} đạt" + (f", bỏ qua {skipped}" if skipped else ""))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "scoring_results.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"passed": passed, "failed": failed, "skipped": skipped, "results": results}, f, ensure_ascii=False, indent=2)
    print("Kết quả lưu tại tests/results/scoring_results.json")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    run()
