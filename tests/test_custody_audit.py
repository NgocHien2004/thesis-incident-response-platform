"""Kiểm thử chain of custody và nhật ký kiểm toán (audit log)."""
import sys, os, json, hashlib, csv, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.scenarios.base import login_all, new_incident

passed = 0
failed = 0
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


def run():
    print("╔══════════════════════════════════════════════╗")
    print("║  KIỂM THỬ CHAIN OF CUSTODY & AUDIT LOG      ║")
    print("╚══════════════════════════════════════════════╝")

    u = login_all()
    analyst, analyst2, it = u["analyst"], u["analyst2"], u["it"]
    inc_id = new_incident(u, "Kiểm thử custody")
    print(f"\n  Dùng incident #{inc_id} (tạo riêng cho bài kiểm thử)\n")

    print("── 1. Thu thập bằng chứng & hash tự động ──")
    content = "SSH Failed password for root from 1.2.3.4 port 22 ssh2 — repeated 500 times"
    expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    ev = it.post(f"/incidents/{inc_id}/evidences/", {
        "title": "Auth log custody test", "evidence_type": "log",
        "source": "webserver01 /var/log/auth.log", "content": content
    })
    check("Tạo bằng chứng thành công", ev is not None)
    if not ev:
        return False
    ev_id = ev["id"]
    check("Hash SHA-256 tự tính đúng", ev.get("file_hash") == expected_hash, f"expected={expected_hash[:16]}...")
    check("Bằng chứng chưa bị lock lúc tạo", ev.get("is_locked") == False)

    print("\n── 2. Chain of custody ghi đúng khi tạo ──")
    custody = analyst.get(f"/incidents/{inc_id}/evidences/{ev_id}/custody")
    check("Chain of custody có dữ liệu", custody is not None and len(custody) > 0)
    if custody:
        first = custody[0]
        check("Action đầu tiên là 'collected'", first.get("action") == "collected")
        check("Ghi đúng người thu thập", first.get("performed_by") is not None)
        check("Ghi đúng thời gian", first.get("performed_at") is not None)

    print("\n── 3. Truy cập bằng chứng → ghi log 'accessed' ──")
    analyst.get(f"/incidents/{inc_id}/evidences/{ev_id}")
    actions = [c["action"] for c in (analyst.get(f"/incidents/{inc_id}/evidences/{ev_id}/custody") or [])]
    check("Chain of custody ghi 'accessed' khi xem", "accessed" in actions, f"actions={actions}")
    n_before = actions.count("accessed")
    analyst2.get(f"/incidents/{inc_id}/evidences/{ev_id}")
    actions = [c["action"] for c in (analyst.get(f"/incidents/{inc_id}/evidences/{ev_id}/custody") or [])]
    check("Analyst khác xem bằng chứng cũng bị ghi lại", actions.count("accessed") == n_before + 1)

    print("\n── 4. Lock bằng chứng ──")
    locked = analyst.patch(f"/incidents/{inc_id}/evidences/{ev_id}/lock")
    check("Lock thành công", locked is not None)
    check("is_locked = True sau khi lock", locked.get("is_locked") == True if locked else False)
    lock_actions = [c["action"] for c in (analyst.get(f"/incidents/{inc_id}/evidences/{ev_id}/custody") or [])]
    check("Chain of custody ghi 'locked'", "locked" in lock_actions, f"actions={lock_actions}")

    print("\n── 5. Sau khi lock — không thể lock lại ──")
    check("Không thể lock bằng chứng đã lock", analyst.patch(f"/incidents/{inc_id}/evidences/{ev_id}/lock") is None,
          "API phải trả về lỗi")

    print("\n── 6. Hash toàn vẹn — nội dung không thay đổi ──")
    detail = analyst.get(f"/incidents/{inc_id}/evidences/{ev_id}")
    check("Hash vẫn giữ nguyên sau lock", detail.get("file_hash") == expected_hash if detail else False)
    check("Nội dung vẫn giữ nguyên", detail.get("content") == content if detail else False)

    print("\n── 7. Lịch sử thông báo đầy đủ ──")
    k = analyst.post(f"/incidents/{inc_id}/communications/", {
        "comm_type": "stakeholder_notify", "subject": "Cập nhật sự cố",
        "content": "Đang xử lý", "recipients": ["stakeholder01"]})
    check("Soạn thông báo", k is not None)
    if k:
        analyst2.patch(f"/incidents/{inc_id}/communications/{k['id']}/approve")
        analyst.patch(f"/incidents/{inc_id}/communications/{k['id']}/send")
    log = analyst.get(f"/incidents/{inc_id}/communications/log")
    check("Communication log có dữ liệu", bool(log))
    if log:
        e = log[0]
        for field in ("subject", "recipients", "sent_at", "status", "is_approved"):
            check(f"Log có {field}", e.get(field) is not None)

    print("\n── 8. Chain of custody đầy đủ theo thứ tự ──")
    final = analyst.get(f"/incidents/{inc_id}/evidences/{ev_id}/custody") or []
    acts = [c["action"] for c in final]
    check("Có đủ 3 action trong custody log", all(a in acts for a in ["collected", "accessed", "locked"]), f"actual={acts}")
    check("Thứ tự đúng: collected trước locked",
          "collected" in acts and "locked" in acts and acts.index("collected") < acts.index("locked"))
    check("Tất cả log có performed_by và performed_at", all(c.get("performed_by") and c.get("performed_at") for c in final))

    print("\n── 9. Nhật ký kiểm toán: ghi đủ ai làm gì, lúc nào ──")
    res = analyst.get(f"/audit/?incident_id={inc_id}&limit=500")
    items = (res or {}).get("items", [])
    by_action = {}
    for i in items:
        by_action.setdefault(i["action"], []).append(i)
    check("Nhật ký có dữ liệu cho incident", len(items) > 0, f"{len(items)} bản ghi")
    ev_created = by_action.get("evidence.created", [])
    check("Ghi việc thu thập bằng chứng", len(ev_created) == 1)
    check("Ghi đúng người thực hiện (it01)", bool(ev_created) and ev_created[0]["username"] == "it01")
    check("Ghi đúng vai trò", bool(ev_created) and ev_created[0]["role"] == "it_helpdesk")
    check("Ghi việc khóa bằng chứng", len(by_action.get("evidence.locked", [])) == 1)
    check("Ghi việc tạo incident", len(by_action.get("incident.created", [])) == 1)
    check("Ghi việc phê duyệt thông báo bởi người khác người soạn",
          any(i["username"] == "analyst02" for i in by_action.get("communication.approved", [])))
    check("Mọi bản ghi có thời gian, người dùng và hành động",
          all(i["at"] and i["username"] and i["action"] for i in items))

    print("\n── 10. Nhật ký không thể sửa hoặc xóa ──")
    check("Không có thao tác xóa", analyst.raw("DELETE", "/audit/1").status_code in (404, 405))
    check("Không có thao tác sửa", analyst.raw("PATCH", "/audit/1", {"detail": "x"}).status_code in (404, 405))
    check("Không có thao tác ghi", analyst.raw("POST", "/audit/", {"action": "x"}).status_code in (404, 405))

    print("\n── 11. Chuỗi băm phát hiện sửa đổi ──")
    v = analyst.get("/audit/verify")
    check("Kiểm tra chuỗi băm thành công", v is not None and v.get("ok") is True,
          f"{v.get('total')} bản ghi" if v else "")
    rows = (analyst.get("/audit/?limit=3") or {}).get("items", [])
    check("Mỗi bản ghi nối với bản ghi trước bằng mã băm (đã kiểm tra ở bước verify)", v is not None and v.get("first_bad_id") is None)

    print("\n── 12. Xuất nhật ký cho kiểm toán ──")
    r = analyst.raw("GET", f"/audit/export.csv?incident_id={inc_id}")
    check("Xuất CSV thành công", r.status_code == 200 and "csv" in r.headers.get("content-type", ""))
    if r.status_code == 200:
        data = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
        check("CSV có tiêu đề và đúng số dòng", len(data) - 1 == res["total"], f"{len(data)-1} dòng")
        check("CSV có cột mã băm", "row_hash" in data[0])

    print("\n── 13. Timeline dựng từ nhật ký ──")
    tl = analyst.get(f"/incidents/{inc_id}/timeline") or []
    labels = [t["label"] for t in tl]
    check("Timeline có sự kiện", len(tl) > 0, f"{len(tl)} sự kiện")
    check("Timeline gồm cả sự kiện cảnh báo trước khi có incident", "Cảnh báo được tạo" in labels)
    check("Timeline gồm thu thập và khóa bằng chứng", "Thu thập bằng chứng" in labels and "Khóa bằng chứng" in labels)
    times = [t["at"] for t in tl]
    check("Timeline sắp theo thời gian", times == sorted(times))

    print(f"\n{'='*50}")
    print(f"KẾT QUẢ: {passed} PASS / {failed} FAIL / {passed+failed} tổng")
    print(f"{'='*50}")
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)
    with open(os.path.join(results_dir, "custody_audit_results.json"), "w", encoding="utf-8") as f:
        json.dump({"passed": passed, "failed": failed, "total": passed + failed,
                   "pass_rate_pct": round(passed / (passed + failed) * 100, 1), "details": results},
                  f, indent=2, ensure_ascii=False)
    print("Kết quả lưu tại tests/results/custody_audit_results.json")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
