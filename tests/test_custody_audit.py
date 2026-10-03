"""
Kiểm thử chain of custody và audit log:
1. Bằng chứng sau khi lock không thể sửa
2. Chain of custody ghi đầy đủ mọi thao tác
3. Audit log toàn vẹn — đủ ai làm gì lúc nào
"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.scenarios.base import ScenarioRunner

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
    results.append({"test": label, "pass": condition, "note": note})

def run():
    print("╔══════════════════════════════════════════════╗")
    print("║  KIỂM THỬ CHAIN OF CUSTODY & AUDIT LOG      ║")
    print("╚══════════════════════════════════════════════╝")

    analyst = ScenarioRunner("analyst01", "Test@1234").login()
    it      = ScenarioRunner("it01",      "Test@1234").login()

    # Lấy incident có sẵn
    incidents = analyst.get("/incidents/")
    inc_id = incidents[0]["id"] if incidents else 1
    print(f"\n  Dùng incident #{inc_id}\n")

    # ══════════════════════════════════════
    print("── 1. Thu thập bằng chứng & hash tự động ──")
    content = "SSH Failed password for root from 1.2.3.4 port 22 ssh2 — repeated 500 times"
    expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    ev = it.post(f"/incidents/{inc_id}/evidences/", {
        "title":         "Auth log custody test",
        "evidence_type": "log",
        "source":        "webserver01 /var/log/auth.log",
        "content":       content
    })
    check("Tạo bằng chứng thành công",        ev is not None)
    if not ev:
        return

    ev_id = ev["id"]
    check("Hash SHA-256 tự tính đúng",         ev.get("file_hash") == expected_hash,
          f"expected={expected_hash[:16]}...")
    check("Bằng chứng chưa bị lock lúc tạo",  ev.get("is_locked") == False)

    # ══════════════════════════════════════
    print("\n── 2. Chain of custody ghi đúng khi tạo ──")
    custody = analyst.get(f"/incidents/{inc_id}/evidences/{ev_id}/custody")
    check("Chain of custody có dữ liệu",       custody is not None and len(custody) > 0)
    if custody:
        first_log = custody[0]
        check("Action đầu tiên là 'collected'", first_log.get("action") == "collected")
        check("Ghi đúng người thu thập",        first_log.get("performed_by") is not None)
        check("Ghi đúng thời gian",             first_log.get("performed_at") is not None)

    # ══════════════════════════════════════
    print("\n── 3. Truy cập bằng chứng → ghi log 'accessed' ──")
    analyst.get(f"/incidents/{inc_id}/evidences/{ev_id}")
    custody_after_access = analyst.get(f"/incidents/{inc_id}/evidences/{ev_id}/custody")
    actions = [c["action"] for c in custody_after_access] if custody_after_access else []
    check("Chain of custody ghi 'accessed' khi xem",
          "accessed" in actions,
          f"actions={actions}")

    # ══════════════════════════════════════
    print("\n── 4. Lock bằng chứng ──")
    locked_ev = analyst.patch(f"/incidents/{inc_id}/evidences/{ev_id}/lock")
    check("Lock thành công",                   locked_ev is not None)
    check("is_locked = True sau khi lock",     locked_ev.get("is_locked") == True if locked_ev else False)

    custody_after_lock = analyst.get(f"/incidents/{inc_id}/evidences/{ev_id}/custody")
    lock_actions = [c["action"] for c in custody_after_lock] if custody_after_lock else []
    check("Chain of custody ghi 'locked'",     "locked" in lock_actions,
          f"actions={lock_actions}")

    # ══════════════════════════════════════
    print("\n── 5. Sau khi lock — không thể lock lại ──")
    lock_again = analyst.patch(f"/incidents/{inc_id}/evidences/{ev_id}/lock")
    check("Không thể lock bằng chứng đã lock", lock_again is None,
          "API phải trả về lỗi")

    # ══════════════════════════════════════
    print("\n── 6. Hash toàn vẹn — nội dung không thay đổi ──")
    ev_detail = analyst.get(f"/incidents/{inc_id}/evidences/{ev_id}")
    check("Hash vẫn giữ nguyên sau lock",
          ev_detail.get("file_hash") == expected_hash if ev_detail else False)
    check("Nội dung vẫn giữ nguyên",
          ev_detail.get("content") == content if ev_detail else False)

    # ══════════════════════════════════════
    print("\n── 7. Audit log communication đầy đủ ──")
    comm_log = analyst.get(f"/incidents/{inc_id}/communications/log")
    check("Communication log có dữ liệu",      comm_log is not None)
    if comm_log and len(comm_log) > 0:
        entry = comm_log[0]
        check("Log có subject",                entry.get("subject") is not None)
        check("Log có recipients",             entry.get("recipients") is not None)
        check("Log có sent_at",                entry.get("sent_at") is not None)
        check("Log có status",                 entry.get("status") is not None)
        check("Log có is_approved",            entry.get("is_approved") is not None)

    # ══════════════════════════════════════
    print("\n── 8. Chain of custody đầy đủ theo thứ tự ──")
    final_custody = analyst.get(f"/incidents/{inc_id}/evidences/{ev_id}/custody")
    if final_custody:
        expected_actions = ["collected", "accessed", "locked"]
        actual_actions   = [c["action"] for c in final_custody]

        check("Có đủ 3 action trong custody log",
              all(a in actual_actions for a in expected_actions),
              f"actual={actual_actions}")
        check("Thứ tự đúng: collected trước locked",
              actual_actions.index("collected") < actual_actions.index("locked")
              if "collected" in actual_actions and "locked" in actual_actions else False)
        check("Tất cả log có performed_by và performed_at",
              all(c.get("performed_by") and c.get("performed_at") for c in final_custody))

    # ══════════════════════════════════════
    print(f"\n{'='*50}")
    print(f"KẾT QUẢ: {passed} PASS / {failed} FAIL / {passed+failed} tổng")
    print(f"{'='*50}")

    os.makedirs("tests", exist_ok=True)
    with open("tests/custody_audit_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "passed":       passed,
            "failed":       failed,
            "total":        passed + failed,
            "pass_rate_pct": round(passed / (passed + failed) * 100, 1),
            "details":      results
        }, f, indent=2, ensure_ascii=False)
    print("Kết quả lưu tại tests/custody_audit_results.json")

if __name__ == "__main__":
    run()