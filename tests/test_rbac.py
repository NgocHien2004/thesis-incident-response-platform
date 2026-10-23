"""Kiểm thử phân quyền RBAC — 3 role (IT/Helpdesk, Analyst/SOC, Stakeholder) và các luật tách nhiệm vụ."""
import sys, os, json, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.scenarios.base import login_all, new_incident, ScenarioRunner

passed = 0
failed = 0
results = []


def expect(label, resp, *codes):
    global passed, failed
    ok = resp.status_code in codes
    passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
    note = "" if ok else f" (nhận {resp.status_code}: {resp.text[:90]})"
    results.append({"test": label, "expected": list(codes), "actual": resp.status_code, "pass": ok})
    print(f"  {'✓ PASS' if ok else '✗ FAIL'} | {label}{note}")
    return ok


BLOCK = (401, 403)


def run():
    print("╔══════════════════════════════════════════════╗")
    print("║  KIỂM THỬ PHÂN QUYỀN RBAC — 3 ROLE          ║")
    print("╚══════════════════════════════════════════════╝")
    u = login_all()
    A, A2, IT, ST = u["analyst"], u["analyst2"], u["it"], u["st"]
    R = lambda who, m, p, body=None: who.raw(m, p, body)
    tag = uuid.uuid4().hex[:6]

    print("\n── 1. Xem dữ liệu (mọi vai trò đăng nhập đều xem được) ──")
    for name, who in (("Analyst", A), ("IT", IT), ("Stakeholder", ST)):
        expect(f"{name} xem incidents", R(who, "GET", "/incidents/"), 200)
        expect(f"{name} xem dashboard", R(who, "GET", "/dashboard/"), 200)

    print("\n── 2. Tạo asset (IT và Analyst; Stakeholder không) ──")
    body = {"name": f"RBAC asset {tag}", "asset_type": "server", "criticality": "low"}
    expect("IT tạo asset", R(IT, "POST", "/assets/", body), 200)
    expect("Analyst tạo asset", R(A, "POST", "/assets/", body), 200)
    expect("Stakeholder tạo asset bị chặn", R(ST, "POST", "/assets/", body), *BLOCK)

    print("\n── 3. Tạo alert (IT và Analyst) ──")
    asset_id = R(IT, "POST", "/assets/", body).json()["id"]
    alert_body = {"title": f"RBAC alert {tag}", "source": "manual", "severity": "low", "affected_asset": asset_id}
    expect("IT tạo alert", R(IT, "POST", "/alerts/", alert_body), 200)
    expect("Analyst tạo alert", R(A, "POST", "/alerts/", alert_body), 200)
    expect("Stakeholder tạo alert bị chặn", R(ST, "POST", "/alerts/", alert_body), *BLOCK)

    print("\n── 4. Triage (IT và Analyst) ──")
    tri = {"triage_type": "test", "triage_severity": "low", "triage_confidence": 50, "triage_sla_hours": 24}
    mk = lambda n: R(IT, "POST", "/alerts/", {**alert_body, "title": f"Triage {n} {tag}"}).json()["id"]
    expect("Analyst triage", R(A, "PATCH", f"/alerts/{mk('a')}/triage", tri), 200)
    expect("IT triage", R(IT, "PATCH", f"/alerts/{mk('b')}/triage", tri), 200)
    expect("Stakeholder triage bị chặn", R(ST, "PATCH", f"/alerts/{mk('c')}/triage", tri), *BLOCK)

    print("\n── 5. Tạo incident (chỉ Analyst) và commander ──")
    def triaged():
        aid = R(IT, "POST", "/alerts/", {**alert_body, "title": f"Inc {uuid.uuid4().hex[:5]}", "ioc": f"{uuid.uuid4().hex[:8]}.example.com"}).json()["id"]
        R(IT, "PATCH", f"/alerts/{aid}/triage", tri)
        return aid
    mkinc = lambda aid, **kw: {"title": "RBAC incident", "severity": "low", "alert_ids": [aid], **kw}
    expect("IT tạo incident bị chặn", R(IT, "POST", "/incidents/", mkinc(triaged())), *BLOCK)
    expect("Stakeholder tạo incident bị chặn", R(ST, "POST", "/incidents/", mkinc(triaged())), *BLOCK)
    expect("Commander không tồn tại bị từ chối", R(A, "POST", "/incidents/", mkinc(triaged(), commander_id=999999)), 400)
    r = R(A, "POST", "/incidents/", mkinc(triaged()))
    expect("Analyst tạo incident", r, 200)
    expect("Commander mặc định là người tạo", type("X", (), {"status_code": 200 if r.json()["commander_id"] == r.json()["created_by"] else 0, "text": ""})(), 200)

    print("\n── 6. Đổi trạng thái incident và bảng chuyển hợp lệ ──")
    inc = r.json()["id"]
    st = lambda who, s, note=None: R(who, "PATCH", f"/incidents/{inc}/status", {"status": s, "note": note})
    expect("IT đổi trạng thái bị chặn", st(IT, "investigating"), *BLOCK)
    expect("Nhảy cóc open → closed bị từ chối", st(A, "closed"), 400)
    expect("Nhảy cóc open → contained bị từ chối", st(A, "contained"), 400)
    expect("Analyst chuyển open → investigating", st(A, "investigating"), 200)
    expect("investigating → contained khi chưa có containment bị từ chối", st(A, "contained"), 400)

    print("\n── 7. Bằng chứng (IT và Analyst) ──")
    ev = {"title": "RBAC evidence", "evidence_type": "log", "content": "x"}
    expect("IT thu thập bằng chứng", R(IT, "POST", f"/incidents/{inc}/evidences/", ev), 200)
    expect("Analyst thu thập bằng chứng", R(A, "POST", f"/incidents/{inc}/evidences/", ev), 200)
    expect("Stakeholder thu thập bị chặn", R(ST, "POST", f"/incidents/{inc}/evidences/", ev), *BLOCK)
    eid = R(IT, "POST", f"/incidents/{inc}/evidences/", ev).json()["id"]
    expect("Stakeholder khóa bằng chứng bị chặn", R(ST, "PATCH", f"/incidents/{inc}/evidences/{eid}/lock"), *BLOCK)
    expect("IT khóa bằng chứng", R(IT, "PATCH", f"/incidents/{inc}/evidences/{eid}/lock"), 200)
    expect("Analyst xem bằng chứng", R(A, "GET", f"/incidents/{inc}/evidences/{eid}"), 200)

    print("\n── 8. Đề xuất containment ──")
    cb = lambda risk="low": {"action_type": "block_ip", "target": "9.9.9.9", "reason": "RBAC", "risk_level": risk}
    expect("Stakeholder đề xuất bị chặn", R(ST, "POST", f"/incidents/{inc}/containments/", cb()), *BLOCK)
    c1 = R(IT, "POST", f"/incidents/{inc}/containments/", cb())
    expect("IT đề xuất containment", c1, 200)
    c2 = R(A, "POST", f"/incidents/{inc}/containments/", cb())
    expect("Analyst đề xuất containment", c2, 200)
    c3 = R(IT, "POST", f"/incidents/{inc}/containments/", cb("high"))
    c1, c2, c3 = c1.json()["id"], c2.json()["id"], c3.json()["id"]
    other = new_incident(u, f"Còn mở {tag}", investigating=False)
    expect("Đề xuất containment khi incident còn 'open' bị từ chối", R(IT, "POST", f"/incidents/{other}/containments/", cb()), 409)

    print("\n── 9. Phê duyệt containment: ma trận thẩm quyền ──")
    rv = lambda who, cid, ok=True: R(who, "PATCH", f"/incidents/{inc}/containments/{cid}/review", {"approved": ok})
    expect("IT phê duyệt bị chặn", rv(IT, c1), *BLOCK)
    expect("Stakeholder phê duyệt bị chặn", rv(ST, c1), *BLOCK)
    expect("Analyst tự duyệt đề xuất của chính mình bị chặn", rv(A, c2), 403)
    expect("Analyst khác duyệt đề xuất rủi ro thấp", rv(A2, c1), 200)
    expect("Rủi ro cao: analyst không phải commander bị chặn", rv(A2, c3), 403)
    expect("Rủi ro cao: commander của vụ được duyệt", rv(A, c3), 200)

    print("\n── 10. Thực hiện và xác minh containment ──")
    ex = lambda who, cid: R(who, "PATCH", f"/incidents/{inc}/containments/{cid}/execute", {"execution_note": "mô phỏng"})
    vf = lambda who, cid: R(who, "PATCH", f"/incidents/{inc}/containments/{cid}/verify", {"verify_note": "ok"})
    expect("Stakeholder thực hiện bị chặn", ex(ST, c1), *BLOCK)
    expect("Xác minh khi chưa thực hiện bị từ chối", vf(A2, c1), 400)
    expect("IT thực hiện containment", ex(IT, c1), 200)
    expect("Analyst thực hiện containment", ex(A, c3), 200)
    expect("IT xác minh bị chặn", vf(IT, c1), *BLOCK)
    expect("Người thực hiện không được tự xác minh", vf(A, c3), 403)
    expect("Analyst khác xác minh containment", vf(A2, c1), 200)
    expect("Analyst khác xác minh containment (rủi ro cao)", vf(A2, c3), 200)

    print("\n── 11. Recovery: chỉ chủ hệ thống xác nhận ──")
    rb = {"action_type": "reset_credentials", "description": "RBAC"}
    expect("Stakeholder tạo recovery bị chặn", R(ST, "POST", f"/incidents/{inc}/recovery/", rb), *BLOCK)
    rec = R(IT, "POST", f"/incidents/{inc}/recovery/", rb)
    expect("IT tạo recovery (incident đã khống chế)", rec, 200)
    rid = rec.json()["id"]
    R(IT, "PATCH", f"/incidents/{inc}/recovery/{rid}/status", {"status": "done"})
    cf = lambda who: R(who, "PATCH", f"/incidents/{inc}/recovery/{rid}/confirm", {"confirm_note": "RBAC"})
    expect("Analyst xác nhận thay chủ hệ thống bị chặn", cf(A), *BLOCK)
    expect("IT xác nhận recovery bị chặn", cf(IT), *BLOCK)
    expect("Stakeholder (chủ hệ thống) xác nhận recovery", cf(ST), 200)
    expect("Tạo recovery khi incident còn 'open' bị từ chối", R(IT, "POST", f"/incidents/{other}/recovery/", rb), 409)

    print("\n── 12. Thông báo: tách người soạn và người duyệt ──")
    cm = lambda t="stakeholder_notify": {"comm_type": t, "subject": "RBAC", "content": "nội dung", "recipients": ["a@x.com"]}
    expect("IT soạn thông báo bị chặn", R(IT, "POST", f"/incidents/{inc}/communications/", cm()), *BLOCK)
    expect("Stakeholder soạn thông báo bị chặn", R(ST, "POST", f"/incidents/{inc}/communications/", cm()), *BLOCK)
    k1 = R(A, "POST", f"/incidents/{inc}/communications/", cm()).json()["id"]
    ap = lambda who, k: R(who, "PATCH", f"/incidents/{inc}/communications/{k}/approve")
    expect("Người soạn tự duyệt bị chặn", ap(A, k1), 403)
    expect("IT duyệt thông báo bị chặn", ap(IT, k1), *BLOCK)
    expect("Analyst khác duyệt thông báo", ap(A2, k1), 200)
    expect("Analyst gửi thông báo đã duyệt", R(A, "PATCH", f"/incidents/{inc}/communications/{k1}/send"), 200)
    ak = lambda who: R(who, "PATCH", f"/incidents/{inc}/communications/{k1}/acknowledge")
    expect("IT xác nhận đã nhận bị chặn", ak(IT), *BLOCK)
    expect("Analyst xác nhận đã nhận bị chặn", ak(A), *BLOCK)
    expect("Stakeholder xác nhận đã nhận", ak(ST), 200)
    k2 = R(A, "POST", f"/incidents/{inc}/communications/", cm("external")).json()["id"]
    expect("Thông báo ra ngoài: không phải commander duyệt bị chặn", ap(A2, k2), 403)

    print("\n── 13. Đóng và mở lại incident: tiêu chí đóng, chỉ commander ──")
    expect("Đóng khi còn đề xuất containment chưa xử lý bị từ chối", st(A, "closed"), 400)
    expect("Analyst từ chối đề xuất tồn đọng", rv(A2, c2, False), 200)
    expect("Analyst không phải commander đóng bị chặn", st(A2, "closed"), 403)
    expect("Commander đóng khi đủ tiêu chí", st(A, "closed"), 200)
    expect("Thêm bằng chứng vào incident đã đóng bị từ chối", R(IT, "POST", f"/incidents/{inc}/evidences/", ev), 409)
    expect("Mở lại không có lý do bị từ chối", st(A, "investigating"), 400)
    expect("Analyst không phải commander mở lại bị chặn", st(A2, "investigating", "thử"), 403)
    expect("Commander mở lại kèm lý do", st(A, "investigating", "Phát hiện thêm máy bị ảnh hưởng"), 200)
    expect("Khống chế lại (đã có containment thực hiện)", st(A, "contained"), 200)
    expect("Commander đóng lại", st(A, "closed"), 200)

    print("\n── 14. Postmortem ──")
    pm = {"root_cause": "Thiếu đào tạo", "timeline": [], "impact": "thấp", "lessons_learned": "x",
          "action_items": [{"task": "Đào tạo", "owner": "it01", "deadline": "2026-12-01", "done": False}],
          "responsible_party": "IT"}
    expect("IT viết postmortem bị chặn", R(IT, "POST", f"/incidents/{inc}/postmortem/", pm), *BLOCK)
    expect("Stakeholder viết postmortem bị chặn", R(ST, "POST", f"/incidents/{inc}/postmortem/", pm), *BLOCK)
    expect("Postmortem khi incident chưa phục hồi bị từ chối", R(A, "POST", f"/incidents/{other}/postmortem/", pm), 400)
    expect("Analyst viết postmortem", R(A, "POST", f"/incidents/{inc}/postmortem/", pm), 200)
    expect("Analyst không phải commander chốt bị chặn", R(A2, "PATCH", f"/incidents/{inc}/postmortem/finalize"), 403)
    expect("Stakeholder đánh dấu action item bị chặn", R(ST, "PATCH", f"/incidents/{inc}/postmortem/action-items/0?done=true"), *BLOCK)
    expect("IT đánh dấu action item", R(IT, "PATCH", f"/incidents/{inc}/postmortem/action-items/0?done=true"), 200)
    expect("Commander chốt postmortem", R(A, "PATCH", f"/incidents/{inc}/postmortem/finalize"), 200)
    expect("Incident vẫn giữ trạng thái đóng sau khi chốt", type("X", (), {"status_code": 200 if R(A, "GET", f"/incidents/{inc}").json()["status"] == "closed" else 0, "text": ""})(), 200)

    print("\n── 15. Xóa asset (chỉ Analyst) ──")
    dels = [R(A, "POST", "/assets/", {"name": f"Del {i} {tag}", "asset_type": "server", "criticality": "low"}).json()["id"] for i in range(4)]
    expect("IT xóa asset bị chặn", R(IT, "DELETE", f"/assets/{dels[0]}"), *BLOCK)
    expect("Stakeholder xóa asset bị chặn", R(ST, "DELETE", f"/assets/{dels[1]}"), *BLOCK)
    expect("Analyst xóa asset", R(A, "DELETE", f"/assets/{dels[3]}"), 200)

    print("\n── 16. Nhật ký kiểm toán và timeline ──")
    expect("Analyst xem nhật ký kiểm toán", R(A, "GET", "/audit/"), 200)
    expect("IT xem nhật ký kiểm toán bị chặn", R(IT, "GET", "/audit/"), *BLOCK)
    expect("Stakeholder xem nhật ký kiểm toán bị chặn", R(ST, "GET", "/audit/"), *BLOCK)
    v = R(A, "GET", "/audit/verify")
    expect("Analyst kiểm tra tính toàn vẹn nhật ký", v, 200)
    expect("Chuỗi băm nhật ký còn nguyên vẹn", type("X", (), {"status_code": 200 if v.json().get("ok") else 0, "text": ""})(), 200)
    expect("IT kiểm tra tính toàn vẹn bị chặn", R(IT, "GET", "/audit/verify"), *BLOCK)
    expect("Analyst xuất nhật ký CSV", R(A, "GET", "/audit/export.csv"), 200)
    expect("Stakeholder xuất nhật ký CSV bị chặn", R(ST, "GET", "/audit/export.csv"), *BLOCK)
    expect("Nhật ký không có thao tác xóa", R(A, "DELETE", "/audit/1"), 404, 405)
    expect("Nhật ký không có thao tác sửa", R(A, "PATCH", "/audit/1", {}), 404, 405)
    for name, who in (("Analyst", A), ("IT", IT), ("Stakeholder", ST)):
        expect(f"{name} xem timeline incident", R(who, "GET", f"/incidents/{inc}/timeline"), 200)

    print("\n── 17. Cấp tài khoản mới (chỉ Analyst) ──")
    nu = lambda who, role="stakeholder": who.raw("POST", "/auth/register", {
        "username": f"tmp_{uuid.uuid4().hex[:8]}", "email": f"{uuid.uuid4().hex[:8]}@example.com",
        "password": "Test@1234", "role": role})
    expect("Không đăng nhập: không tạo được tài khoản", ScenarioRunner("x", "y").raw("POST", "/auth/register", {
        "username": f"tmp_{tag}", "email": f"{tag}@example.com", "password": "Test@1234", "role": "analyst_soc"}), 401)
    expect("IT cấp tài khoản bị chặn", nu(IT), *BLOCK)
    expect("Stakeholder cấp tài khoản bị chặn", nu(ST), *BLOCK)
    expect("Analyst cấp tài khoản", nu(A), 200)

    print("\n── 18. Gọi AI (mọi vai trò có token) ──")
    ai = {"title": "test", "description": "test", "ioc": ""}
    for name, who in (("Analyst", A), ("IT", IT), ("Stakeholder", ST)):
        expect(f"{name} gọi AI suggest", R(who, "POST", "/ai/alert/suggest", ai), 200)

    print("\n── 19. Không có token ──")
    anon = ScenarioRunner("x", "y")
    for p in ("/incidents/", "/alerts/", "/dashboard/", "/audit/"):
        expect(f"Không token truy cập {p}", anon.raw("GET", p), 401, 403)

    print(f"\n{'='*50}")
    print(f"KẾT QUẢ: {passed} PASS / {failed} FAIL / {passed+failed} tổng")
    print(f"{'='*50}")
    os.makedirs("tests", exist_ok=True)
    with open("tests/rbac_results.json", "w", encoding="utf-8") as f:
        json.dump({"passed": passed, "failed": failed, "total": passed + failed,
                   "pass_rate_pct": round(passed / (passed + failed) * 100, 1), "details": results},
                  f, indent=2, ensure_ascii=False)
    print("Kết quả lưu tại tests/rbac_results.json")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
