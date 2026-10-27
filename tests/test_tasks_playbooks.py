import sys, os, json, uuid, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.scenarios.base import login_all, new_incident

passed = 0
failed = 0
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


def run():
    print("╔══════════════════════════════════════════════╗")
    print("║  KIỂM THỬ PLAYBOOK VÀ CÔNG VIỆC (TASK)       ║")
    print("╚══════════════════════════════════════════════╝")
    u = login_all()
    A, A2, IT, ST = u["analyst"], u["analyst2"], u["it"], u["st"]
    R = lambda who, m, p, body=None: who.raw(m, p, body)
    tag = uuid.uuid4().hex[:6]

    def uid(runner):
        part = runner.token.split(".")[1]
        return int(json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))["sub"])

    me = {"A": uid(A), "A2": uid(A2), "IT": uid(IT), "ST": uid(ST)}

    print("\n── 1. Playbook: xem và quản lý ──")
    lst = R(A, "GET", "/playbooks/")
    expect("Analyst xem danh sách playbook", lst, 200)
    expect("IT xem danh sách playbook", R(IT, "GET", "/playbooks/"), 200)
    expect("Stakeholder xem danh sách playbook", R(ST, "GET", "/playbooks/"), 200)
    pbs = lst.json()
    types = {p["incident_type"] for p in pbs}
    check("Có đủ 4 playbook mẫu (phishing, credential, malware, web attack)",
          {"phishing", "credential_compromise", "malware", "web_attack"} <= types)
    phishing = next(p for p in pbs if p["incident_type"] == "phishing")
    detail = R(A, "GET", f"/playbooks/{phishing['id']}")
    expect("Xem chi tiết playbook", detail, 200)
    steps = detail.json()["steps"]
    check("Các bước của playbook đánh số liên tiếp từ 1",
          [s["step_order"] for s in steps] == list(range(1, len(steps) + 1)))
    check("Playbook mẫu có công việc bắt buộc và không bắt buộc", 0 < phishing["required_count"] < phishing["step_count"])
    ref = next((p for p in pbs if "Tham chiếu chuẩn" in p["name"]), None)
    check("Có playbook tham chiếu chuẩn theo CISA", ref is not None)
    if ref:
        rd = R(A, "GET", f"/playbooks/{ref['id']}").json()
        check("Playbook tham chiếu có đủ 6 giai đoạn",
              {s["phase"] for s in rd["steps"]} == {"analysis", "evidence", "containment", "recovery", "communication", "closure"})
        check("Mọi bước của playbook tham chiếu có mã mục CISA ở trường riêng",
              all((s.get("reference") or "").startswith("CISA B ") for s in rd["steps"]))
        check("Mô tả bước không bị lẫn mã tham chiếu", not any("Tham chiếu:" in (s["description"] or "") for s in rd["steps"]))
        check("Mô tả playbook tham chiếu ngắn gọn, không kể lai lịch", len(rd["description"] or "") < 400 and "1d" not in (rd["description"] or ""))
        check("Playbook tham chiếu nêu nguồn CISA và NIST", "CISA" in (rd["source"] or "") and "NIST" in (rd["source"] or ""))
    expect("Playbook không tồn tại trả 404", R(A, "GET", "/playbooks/999999"), 404)

    new_pb = {
        "name": f"Playbook kiểm thử {tag}", "incident_type": "other", "description": "test",
        "steps": [
            {"title": "Bước A", "phase": "analysis", "owner_role": "analyst_soc", "due_hours": 2, "is_required": True, "reference": "Mã thử A"},
            {"title": "Bước B", "phase": "recovery", "owner_role": "it_helpdesk", "due_hours": 24, "is_required": False},
        ],
    }
    expect("IT tạo playbook bị chặn", R(IT, "POST", "/playbooks/", new_pb), *BLOCK)
    expect("Stakeholder tạo playbook bị chặn", R(ST, "POST", "/playbooks/", new_pb), *BLOCK)
    made = R(A, "POST", "/playbooks/", new_pb)
    expect("Analyst tạo playbook", made, 200)
    pid = made.json()["id"]
    expect("Tạo playbook trùng tên bị từ chối", R(A, "POST", "/playbooks/", new_pb), 400)
    bad = {**new_pb, "name": f"Sai vai trò {tag}",
           "steps": [{"title": "X", "phase": "analysis", "owner_role": "stakeholder"}]}
    expect("Giao bước cho Stakeholder bị từ chối", R(A, "POST", "/playbooks/", bad), 422)
    expect("Playbook không có bước nào bị từ chối", R(A, "POST", "/playbooks/", {**new_pb, "name": f"Rỗng {tag}", "steps": []}), 422)

    check("Tạo playbook lưu mã tham chiếu của bước", made.json()["steps"][0]["reference"] == "Mã thử A")
    upd = {**new_pb, "steps": [new_pb["steps"][0]], "is_active": True}
    expect("IT sửa playbook bị chặn", R(IT, "PUT", f"/playbooks/{pid}", upd), *BLOCK)
    r = R(A, "PUT", f"/playbooks/{pid}", upd)
    expect("Analyst sửa playbook (thay toàn bộ bước)", r, 200)
    check("Sau khi sửa playbook còn 1 bước", r.json()["step_count"] == 1)
    check("Sửa playbook giữ nguyên mã tham chiếu", r.json()["steps"][0]["reference"] == "Mã thử A")

    print("\n── 2. Áp dụng playbook cho incident ──")
    inc = new_incident(u, f"Task kiểm thử {tag}")
    ap = lambda who, pb, i=None: R(who, "POST", f"/incidents/{i or inc}/tasks/apply-playbook", {"playbook_id": pb})
    expect("IT áp dụng playbook bị chặn", ap(IT, phishing["id"]), *BLOCK)
    expect("Stakeholder áp dụng playbook bị chặn", ap(ST, phishing["id"]), *BLOCK)
    expect("Áp dụng playbook không tồn tại bị từ chối", ap(A, 999999), 404)
    r = ap(A, phishing["id"])
    expect("Analyst áp dụng playbook phishing", r, 200)
    body = r.json()
    check("Số công việc tạo ra bằng số bước của playbook", body["created"] == phishing["step_count"])
    tasks = R(A, "GET", f"/incidents/{inc}/tasks/").json()
    check("Công việc có hạn (due_at) tính từ lúc tạo vụ", all(t["due_at"] for t in tasks))
    check("Công việc mới đều ở trạng thái todo", all(t["status"] == "todo" for t in tasks))
    r2 = ap(A, phishing["id"])
    check("Áp dụng lại cùng playbook không tạo trùng",
          r2.status_code == 200 and r2.json()["created"] == 0 and r2.json()["already_present"] == phishing["step_count"])
    if ref:
        inc_ref = new_incident(u, f"Playbook tham chiếu {tag}")
        r = ap(A, ref["id"], inc_ref)
        check("Áp dụng playbook tham chiếu tạo đủ công việc",
              r.status_code == 200 and r.json()["created"] == ref["step_count"])
    R(A, "PUT", f"/playbooks/{pid}", {**upd, "is_active": False})
    expect("Áp dụng playbook đã ngừng dùng bị từ chối", ap(A, pid), 400)
    check("active_only bỏ qua playbook đã ngừng dùng",
          pid not in [p["id"] for p in R(A, "GET", "/playbooks/?active_only=true").json()])

    print("\n── 3. Tạo incident kèm playbook ──")
    asset = R(IT, "POST", "/assets/", {"name": f"Task asset {tag}", "asset_type": "server", "criticality": "low"}).json()["id"]
    mk_alert = lambda: R(IT, "POST", "/alerts/", {"title": f"Task alert {uuid.uuid4().hex[:5]}", "source": "manual", "severity": "high",
                                                  "ioc": f"t-{uuid.uuid4().hex[:8]}.example.com", "affected_asset": asset}).json()["id"]
    tri = {"triage_type": "phishing", "triage_severity": "high", "triage_confidence": 70, "triage_sla_hours": 8}

    def alert_ready():
        aid = mk_alert()
        R(IT, "PATCH", f"/alerts/{aid}/triage", tri)
        return aid

    c = R(A, "POST", "/incidents/", {"title": f"Có playbook {tag}", "severity": "high", "alert_ids": [alert_ready()],
                                     "playbook_id": phishing["id"]})
    expect("Tạo incident kèm playbook", c, 200)
    n_tasks = len(R(A, "GET", f"/incidents/{c.json()['id']}/tasks/").json())
    check("Incident mới có sẵn công việc từ playbook", n_tasks == phishing["step_count"])
    expect("Tạo incident với playbook không tồn tại bị từ chối",
           R(A, "POST", "/incidents/", {"title": "x", "severity": "low", "alert_ids": [alert_ready()], "playbook_id": 999999}), 404)
    expect("Tạo incident với playbook đã ngừng dùng bị từ chối",
           R(A, "POST", "/incidents/", {"title": "x", "severity": "low", "alert_ids": [alert_ready()], "playbook_id": pid}), 400)
    plain = new_incident(u, f"Không playbook {tag}")
    check("Incident tạo không kèm playbook thì không có công việc", R(A, "GET", f"/incidents/{plain}/tasks/").json() == [])

    print("\n── 4. Quyền và luật chuyển trạng thái của công việc ──")
    tasks = R(A, "GET", f"/incidents/{inc}/tasks/").json()
    t_it = next(t for t in tasks if t["owner_role"] == "it_helpdesk" and t["is_required"])
    t_an = next(t for t in tasks if t["owner_role"] == "analyst_soc" and t["is_required"])
    t_opt = next(t for t in tasks if not t["is_required"])
    tp = lambda who, t, body, i=None: R(who, "PATCH", f"/incidents/{i or inc}/tasks/{t['id']}", body)

    expect("Stakeholder đổi trạng thái công việc bị chặn", tp(ST, t_it, {"status": "in_progress"}), *BLOCK)
    expect("IT nhận việc chưa giao của IT", tp(IT, t_it, {"status": "in_progress"}), 200)
    after = next(t for t in R(A, "GET", f"/incidents/{inc}/tasks/").json() if t["id"] == t_it["id"])
    check("Nhận việc tự gán người làm là chính mình", after["assignee_id"] == me["IT"])
    expect("IT làm việc chưa giao của Analyst bị chặn", tp(IT, t_an, {"status": "in_progress"}), 403)
    expect("IT giao việc bị chặn", tp(IT, t_an, {"assignee_id": me["IT"]}), 403)
    expect("IT đặt hạn bị chặn", tp(IT, t_an, {"due_at": "2030-01-01T00:00:00"}), 403)
    expect("Đặt trạng thái trùng trạng thái hiện tại bị từ chối", tp(IT, t_it, {"status": "in_progress"}), 400)
    expect("IT bỏ qua công việc bị chặn", tp(IT, t_it, {"status": "skipped", "note": "x"}), 403)
    expect("IT hoàn thành việc của mình", tp(IT, t_it, {"status": "done"}), 200)
    expect("IT mở lại việc đã xong bị chặn", tp(IT, t_it, {"status": "in_progress", "note": "x"}), 403)
    expect("IT xem danh sách người được giao việc bị chặn", R(IT, "GET", f"/incidents/{inc}/tasks/assignees"), *BLOCK)
    asg = R(A, "GET", f"/incidents/{inc}/tasks/assignees")
    expect("Analyst xem danh sách người được giao việc", asg, 200)
    check("Danh sách người được giao việc chỉ có IT và Analyst",
          asg.status_code == 200 and {x["role"] for x in asg.json()} <= {"it_helpdesk", "analyst_soc"}
          and me["IT"] in [x["id"] for x in asg.json()] and me["ST"] not in [x["id"] for x in asg.json()])
    expect("Analyst giao việc cho IT", tp(A, t_an, {"assignee_id": me["IT"]}), 200)
    expect("Giao việc cho Stakeholder bị từ chối", tp(A, t_an, {"assignee_id": me["ST"]}), 400)
    expect("IT làm việc đã được giao cho mình", tp(IT, t_an, {"status": "in_progress"}), 200)
    expect("Chuyển công việc đã xong thẳng về todo bị từ chối",
           tp(A, t_it, {"status": "todo"}), 400)

    expect("Mở lại việc đã xong không có lý do bị từ chối", tp(A, t_it, {"status": "in_progress"}), 400)
    expect("Analyst mở lại việc đã xong kèm lý do", tp(A, t_it, {"status": "in_progress", "note": "Cần làm lại"}), 200)
    expect("Bỏ qua việc không có lý do bị từ chối", tp(A2, t_opt, {"status": "skipped"}), 400)
    expect("Analyst bỏ qua việc không bắt buộc kèm lý do", tp(A2, t_opt, {"status": "skipped", "note": "Không áp dụng"}), 200)
    expect("Analyst không phải commander bỏ qua việc bắt buộc bị chặn", tp(A2, t_an, {"status": "skipped", "note": "x"}), 403)
    expect("Commander bỏ qua việc bắt buộc kèm lý do", tp(A, t_an, {"status": "skipped", "note": "Đã xử lý bằng cách khác"}), 200)
    expect("Analyst không phải commander mở lại việc bắt buộc đã bỏ qua bị chặn", tp(A2, t_an, {"status": "todo"}), 403)
    expect("Commander mở lại việc bắt buộc đã bỏ qua", tp(A, t_an, {"status": "todo"}), 200)
    expect("Công việc của incident khác trả 404", tp(A, t_an, {"status": "done"}, i=plain), 404)

    print("\n── 5. Công việc tạo tay ──")
    mt = {"title": f"Việc thủ công {tag}", "phase": "evidence", "is_required": False, "due_hours": 4}
    expect("IT tạo công việc thủ công bị chặn", R(IT, "POST", f"/incidents/{inc}/tasks/", mt), *BLOCK)
    expect("Stakeholder tạo công việc thủ công bị chặn", R(ST, "POST", f"/incidents/{inc}/tasks/", mt), *BLOCK)
    expect("Tạo công việc giao cho Stakeholder bị từ chối",
           R(A, "POST", f"/incidents/{inc}/tasks/", {**mt, "assignee_id": me["ST"]}), 400)
    made = R(A, "POST", f"/incidents/{inc}/tasks/", mt)
    expect("Analyst tạo công việc thủ công", made, 200)
    manual = made.json()
    expect("IT xóa công việc bị chặn", R(IT, "DELETE", f"/incidents/{inc}/tasks/{manual['id']}"), *BLOCK)
    expect("Xóa công việc từ playbook bị từ chối", R(A, "DELETE", f"/incidents/{inc}/tasks/{t_it['id']}"), 400)
    R(A, "PATCH", f"/incidents/{inc}/tasks/{manual['id']}", {"status": "done"})
    expect("Xóa công việc đã hoàn thành bị từ chối", R(A, "DELETE", f"/incidents/{inc}/tasks/{manual['id']}"), 400)
    other_manual = R(A, "POST", f"/incidents/{inc}/tasks/", mt).json()
    expect("Analyst xóa công việc thủ công chưa xong", R(A, "DELETE", f"/incidents/{inc}/tasks/{other_manual['id']}"), 200)

    print("\n── 6. Tổng hợp, dashboard, timeline ──")
    s = R(A, "GET", f"/incidents/{inc}/tasks/summary")
    expect("Xem tổng hợp công việc", s, 200)
    sj = s.json()
    check("Tổng hợp: số liệu nhất quán (open_required ≤ required ≤ total)",
          sj["open_required"] <= sj["required"] <= sj["total"] and sj["total"] > 0)
    dash = R(ST, "GET", "/dashboard/").json()
    check("Dashboard có thống kê công việc", set(dash.get("tasks", {})) >= {"open", "open_required", "overdue"})
    tl = R(A, "GET", f"/incidents/{inc}/timeline").json()
    labels = {x["label"] for x in tl}
    check("Timeline ghi các sự kiện công việc", {"Tạo công việc", "Hoàn thành công việc", "Bỏ qua công việc"} <= labels)

    print("\n── 7. Công việc bắt buộc chặn việc đóng incident ──")
    cb = {"action_type": "block_ip", "target": "9.9.9.9", "reason": "test", "risk_level": "low"}
    cid = R(IT, "POST", f"/incidents/{inc}/containments/", cb).json()["id"]
    R(A2, "PATCH", f"/incidents/{inc}/containments/{cid}/review", {"approved": True})
    R(IT, "PATCH", f"/incidents/{inc}/containments/{cid}/execute", {"execution_note": "mô phỏng"})
    R(A2, "PATCH", f"/incidents/{inc}/containments/{cid}/verify", {"verify_note": "ok"})
    rid = R(IT, "POST", f"/incidents/{inc}/recovery/", {"action_type": "reset_credentials", "description": "test"}).json()["id"]
    R(IT, "PATCH", f"/incidents/{inc}/recovery/{rid}/status", {"status": "done"})
    R(ST, "PATCH", f"/incidents/{inc}/recovery/{rid}/confirm", {"confirm_note": "ok"})
    close = lambda: R(A, "PATCH", f"/incidents/{inc}/status", {"status": "closed"})
    r = close()
    expect("Đóng khi còn công việc bắt buộc chưa xong bị từ chối", r, 400)
    check("Thông báo lỗi nêu công việc bắt buộc", "công việc bắt buộc" in r.text)
    for t in R(A, "GET", f"/incidents/{inc}/tasks/").json():
        if t["is_required"] and t["status"] in ("todo", "in_progress"):
            tp(A, t, {"status": "done"})
    expect("Đóng được khi mọi công việc bắt buộc đã xong", close(), 200)
    expect("Đổi trạng thái công việc của incident đã đóng bị từ chối", tp(A, t_opt, {"status": "todo"}), 409)
    expect("Tạo công việc cho incident đã đóng bị từ chối", R(A, "POST", f"/incidents/{inc}/tasks/", mt), 409)
    expect("Áp dụng playbook cho incident đã đóng bị từ chối", ap(A, phishing["id"]), 409)

    print("\n── 8. Nhật ký kiểm toán vẫn nguyên vẹn ──")
    v = R(A, "GET", "/audit/verify").json()
    check("Chuỗi băm nhật ký kiểm toán nguyên vẹn", v.get("ok") is True)

    print("\n" + "=" * 50)
    print(f"KẾT QUẢ: {passed}/{passed + failed} đạt")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks_playbooks_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"passed": passed, "failed": failed, "results": results}, f, ensure_ascii=False, indent=2)
    print("Kết quả lưu tại tests/tasks_playbooks_results.json")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    run()
