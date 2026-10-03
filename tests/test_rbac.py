"""
Kiểm thử phân quyền RBAC — 3 role: IT/Helpdesk, Analyst/SOC, Stakeholder.
Mỗi test kiểm tra endpoint có chặn đúng role không.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.scenarios.base import ScenarioRunner

# ── Kết quả ──
passed = 0
failed = 0
results = []

def check(label, response, expect_ok: bool):
    global passed, failed
    if response is None:
        actual_ok = False
    else:
        actual_ok = True

    ok = actual_ok == expect_ok
    status = "✓ PASS" if ok else "✗ FAIL"
    if ok:
        passed += 1
    else:
        failed += 1

    result = {
        "test":     label,
        "expected": "allowed" if expect_ok else "blocked",
        "actual":   "allowed" if actual_ok else "blocked",
        "pass":     ok
    }
    results.append(result)
    print(f"  {status} | {label}")
    return ok

def run():
    print("╔══════════════════════════════════════════════╗")
    print("║  KIỂM THỬ PHÂN QUYỀN RBAC — 3 ROLE          ║")
    print("╚══════════════════════════════════════════════╝")

    analyst    = ScenarioRunner("analyst01",    "Test@1234").login()
    it         = ScenarioRunner("it01",         "Test@1234").login()
    stakeholder= ScenarioRunner("stakeholder01","Test@1234").login()

    # Lấy incident và alert có sẵn để test
    incidents = analyst.get("/incidents/")
    inc_id = incidents[0]["id"] if incidents else 1
    alerts = analyst.get("/alerts/")
    alert_id = alerts[0]["id"] if alerts else 1

    print(f"\n  Dùng incident #{inc_id}, alert #{alert_id} để test\n")

    # ══════════════════════════════════════
    print("── 1. Xem dữ liệu (tất cả role được xem) ──")
    check("IT xem danh sách incidents",       it.get("/incidents/"),          True)
    check("Stakeholder xem danh sách alerts", stakeholder.get("/alerts/"),    True)
    check("Analyst xem dashboard",            analyst.get("/dashboard/"),     True)
    check("IT xem dashboard",                 it.get("/dashboard/"),          True)
    check("Stakeholder xem dashboard",        stakeholder.get("/dashboard/"), True)

    # ══════════════════════════════════════
    print("\n── 2. Tạo asset (IT và Analyst được, Stakeholder không) ──")
    asset_payload = {
        "name": "Test Server RBAC",
        "asset_type": "server",
        "criticality": "low"
    }
    check("IT tạo asset",          it.post("/assets/", asset_payload),          True)
    check("Analyst tạo asset",     analyst.post("/assets/", asset_payload),     True)
    check("Stakeholder tạo asset", stakeholder.post("/assets/", asset_payload), False)

    # ══════════════════════════════════════
    print("\n── 3. Tạo alert (IT và Analyst được, Stakeholder không) ──")
    alert_payload = {
        "title": "RBAC Test Alert",
        "source": "manual",
        "severity": "low",
        "affected_asset": 1
    }
    check("IT tạo alert",          it.post("/alerts/", alert_payload),          True)
    check("Analyst tạo alert",     analyst.post("/alerts/", alert_payload),     True)
    check("Stakeholder tạo alert", stakeholder.post("/alerts/", alert_payload), False)

    # ══════════════════════════════════════
    print("\n── 4. Triage alert (chỉ Analyst) ──")
    # Lấy alert mới tạo ở trên
    new_alerts = analyst.get("/alerts/?status=new")
    test_alert_id = new_alerts[-1]["id"] if new_alerts else alert_id

    triage_payload = {
        "triage_type": "test",
        "triage_severity": "low",
        "triage_confidence": 50,
        "triage_sla_hours": 24,
    }
    check("Analyst triage alert",     analyst.patch(f"/alerts/{test_alert_id}/triage", triage_payload),     True)
    check("IT triage alert",          it.patch(f"/alerts/{test_alert_id}/triage", triage_payload),          False)
    check("Stakeholder triage alert", stakeholder.patch(f"/alerts/{test_alert_id}/triage", triage_payload), False)

    # ══════════════════════════════════════
    print("\n── 5. Tạo incident (chỉ Analyst) ──")
    # Cần alert đã triage
    triaged = analyst.get(f"/alerts/{test_alert_id}")
    if triaged and triaged.get("status") == "triaged":
        inc_payload = {
            "title": "RBAC Test Incident",
            "severity": "low",
            "commander_id": 1,
            "alert_ids": [test_alert_id]
        }
        check("Analyst tạo incident",     analyst.post("/incidents/", inc_payload),     True)
        check("IT tạo incident",          it.post("/incidents/", inc_payload),          False)
        check("Stakeholder tạo incident", stakeholder.post("/incidents/", inc_payload), False)
    else:
        print("  SKIP — không có alert đã triage để test")

    # ══════════════════════════════════════
    print("\n── 6. Đề xuất containment (IT và Analyst được) ──")
    cont_payload = {
        "action_type": "block_ip",
        "target": "9.9.9.9",
        "reason": "RBAC test",
        "risk_level": "low"
    }
    check("IT đề xuất containment",          it.post(f"/incidents/{inc_id}/containments/", cont_payload),          True)
    check("Analyst đề xuất containment",     analyst.post(f"/incidents/{inc_id}/containments/", cont_payload),     True)
    check("Stakeholder đề xuất containment", stakeholder.post(f"/incidents/{inc_id}/containments/", cont_payload), False)

    # ══════════════════════════════════════
    print("\n── 7. Phê duyệt containment (chỉ Analyst) ──")
    conts = analyst.get(f"/incidents/{inc_id}/containments/")
    if conts:
        proposed = [c for c in conts if c["status"] == "proposed"]
        if proposed:
            cont_id = proposed[0]["id"]
            review_payload = {"approved": True, "review_note": "RBAC test"}
            check("Analyst phê duyệt containment",     analyst.patch(f"/incidents/{inc_id}/containments/{cont_id}/review", review_payload),     True)
            check("IT phê duyệt containment",          it.patch(f"/incidents/{inc_id}/containments/{cont_id}/review", review_payload),          False)
            check("Stakeholder phê duyệt containment", stakeholder.patch(f"/incidents/{inc_id}/containments/{cont_id}/review", review_payload), False)

    # ══════════════════════════════════════
    print("\n── 8. Xác nhận recovery (Stakeholder và Analyst được) ──")
    recs = analyst.get(f"/incidents/{inc_id}/recovery/")
    if recs:
        done_recs = [r for r in recs if r["status"] == "done" and not r["is_confirmed"]]
        if done_recs:
            rec_id = done_recs[0]["id"]
            check("Stakeholder xác nhận recovery", stakeholder.patch(f"/incidents/{inc_id}/recovery/{rec_id}/confirm", {"confirm_note": "RBAC test"}), True)
        else:
            print("  SKIP — không có recovery action done chưa confirm")
    else:
        print("  SKIP — không có recovery action")

    # ══════════════════════════════════════
    print("\n── 9. Xóa asset (chỉ Analyst) ──")
    import requests
    def delete(runner, path):
        try:
            resp = requests.delete(
                f"http://localhost:8000{path}",
                headers=runner.headers()
            )
            return resp.status_code

        except Exception:
            return 500

    # Tạo 3 asset riêng để test xóa
    a1 = analyst.post("/assets/", {"name": "Del Test 1", "asset_type": "server", "criticality": "low"})
    a2 = analyst.post("/assets/", {"name": "Del Test 2", "asset_type": "server", "criticality": "low"})
    a3 = analyst.post("/assets/", {"name": "Del Test 3", "asset_type": "server", "criticality": "low"})

    if a1 and a2 and a3:
        # IT xóa → phải bị 403
        check("IT xóa asset bị chặn",          delete(it, f"/assets/{a1['id']}") == 403,          True)
        # Stakeholder xóa → phải bị 403
        check("Stakeholder xóa asset bị chặn", delete(stakeholder, f"/assets/{a2['id']}") == 403, True)
        # Analyst xóa → phải được 200
        check("Analyst xóa asset thành công",  delete(analyst, f"/assets/{a3['id']}") == 200,     True)

    # ══════════════════════════════════════
    print("\n── 10. Gọi AI (tất cả role có token đều được) ──")
    ai_payload = {"title": "test", "description": "test", "ioc": ""}
    check("Analyst gọi AI suggest",     analyst.post("/ai/alert/suggest", ai_payload),     True)
    check("IT gọi AI suggest",          it.post("/ai/alert/suggest", ai_payload),          True)
    check("Stakeholder gọi AI suggest", stakeholder.post("/ai/alert/suggest", ai_payload), True)

    # ══════════════════════════════════════
    print("\n── 11. Không có token (unauthenticated) ──")
    import requests
    def no_auth_get(path):
        try:
            resp = requests.get(f"http://localhost:8000{path}")
            return None if resp.status_code == 401 else resp.json()
        except Exception:
            return None

    check("Unauthenticated xem incidents", no_auth_get("/incidents/"), False)
    check("Unauthenticated xem alerts",    no_auth_get("/alerts/"),    False)
    check("Unauthenticated xem dashboard", no_auth_get("/dashboard/"), False)

    # ══════════════════════════════════════
    print(f"\n{'='*50}")
    print(f"KẾT QUẢ: {passed} PASS / {failed} FAIL / {passed+failed} tổng")
    print(f"{'='*50}")

    # Lưu kết quả
    os.makedirs("tests", exist_ok=True)
    with open("tests/rbac_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "passed": passed,
            "failed": failed,
            "total":  passed + failed,
            "pass_rate_pct": round(passed / (passed + failed) * 100, 1),
            "details": results
        }, f, indent=2, ensure_ascii=False)
    print("Kết quả lưu tại tests/rbac_results.json")

if __name__ == "__main__":
    run()