from tests.scenarios.base import ScenarioRunner
import time

def run():
    print("\n" + "="*60)
    print("KỊCH BẢN 2 — Credential Compromise")
    print("="*60)

    r    = ScenarioRunner("analyst01", "Test@1234").login()
    r_it = ScenarioRunner("it01", "Test@1234").login()
    r_st = ScenarioRunner("stakeholder01", "Test@1234").login()

    r.tick("start")

    # Alert
    print("\n[1] Tạo alert...")
    alert = r_it.post("/alerts/", {
        "title": "Impossible travel login detected",
        "description": "Account admin logged in from Vietnam at 02:00 then USA at 02:05 — impossible travel",
        "source": "ids_ips",
        "severity": "critical",
        "ioc": "185.220.101.5,admin",
        "affected_asset": 1
    })
    if not alert: return None
    alert_id = alert["id"]
    r.tick("alert_created")

    # Triage
    print("\n[2] Triage...")
    r.tick("triage_start")
    r.patch(f"/alerts/{alert_id}/triage", {
        "triage_type": "credential_compromise",
        "triage_severity": "critical",
        "triage_confidence": 95,
        "triage_assignee": 1,
        "triage_sla_hours": 1,
        "triage_note": "Impossible travel — tài khoản admin bị chiếm"
    })
    r.tick("triage_done")
    triage_time = r.elapsed("triage_start", "triage_done")

    # Incident
    print("\n[3] Tạo incident...")
    incident = r.post("/incidents/", {
        "title": "Admin account credential compromise",
        "description": "Tài khoản admin bị đăng nhập từ IP nước ngoài",
        "severity": "critical",
        "commander_id": 1,
        "alert_ids": [alert_id]
    })
    if not incident: return None
    inc_id = incident["id"]

    # Evidence
    r_it.post(f"/incidents/{inc_id}/evidences/", {
        "title": "Authentication log",
        "evidence_type": "log",
        "source": "Active Directory",
        "content": "02:00 - Login success admin from 1.2.3.4 (Vietnam)\n02:05 - Login success admin from 185.220.101.5 (USA/Tor)"
    })

    # Impact
    r.post(f"/incidents/{inc_id}/impact/", {
        "ioc_list": ["185.220.101.5"],
        "affected_assets": [1],
        "affected_accounts": ["admin"],
        "attck_techniques": ["T1078", "T1110"],
        "attck_version": "14.1",
        "summary": "Tài khoản admin bị chiếm từ Tor exit node, kỹ thuật T1078 Valid Accounts"
    })

    # Containment
    r.patch(f"/incidents/{inc_id}/status", {"status": "investigating"})
    cont = r_it.post(f"/incidents/{inc_id}/containments/", {
        "action_type": "lock_account",
        "target": "admin",
        "reason": "Tài khoản bị đăng nhập từ IP Tor đáng ngờ",
        "risk_level": "high"
    })
    if cont:
        r.patch(f"/incidents/{inc_id}/containments/{cont['id']}/review", {
            "approved": True, "review_note": "Xác nhận compromise, khóa ngay"
        })
        r_it.patch(f"/incidents/{inc_id}/containments/{cont['id']}/execute", {
            "execution_note": "Khóa tài khoản admin, revoke tất cả session (mô phỏng)"
        })

    # Recovery
    rec = r_it.post(f"/incidents/{inc_id}/recovery/", {
        "action_type": "reset_credentials",
        "description": "Reset credential admin, bật MFA bắt buộc",
        "assigned_to": 2
    })
    if rec:
        r_it.patch(f"/incidents/{inc_id}/recovery/{rec['id']}/status", {
            "status": "done", "note": "Reset xong, MFA đã bật"
        })
        r_st.patch(f"/incidents/{inc_id}/recovery/{rec['id']}/confirm", {
            "confirm_note": "Xác nhận tài khoản admin đã được bảo vệ lại"
        })

    # Postmortem
    pm = r.post(f"/incidents/{inc_id}/postmortem/", {
        "root_cause": "Không có MFA trên tài khoản admin, mật khẩu yếu bị brute force",
        "timeline": [
            {"time": "02:00", "event": "Login bình thường từ Việt Nam", "actor": "admin"},
            {"time": "02:05", "event": "Login từ Tor exit node USA", "actor": "attacker"},
            {"time": "02:10", "event": "IDS phát hiện impossible travel", "actor": "system"},
            {"time": "02:30", "event": "Analyst khóa tài khoản", "actor": "analyst01"},
        ],
        "impact": "Tài khoản admin bị truy cập trái phép ~5 phút, không rõ dữ liệu bị lấy",
        "lessons_learned": "Bắt buộc MFA cho tất cả tài khoản đặc quyền",
        "action_items": [
            {"task": "Bật MFA cho tất cả admin accounts", "owner": "it01", "deadline": "2026-10-05", "done": False},
            {"task": "Review và rotate tất cả service account passwords", "owner": "it01", "deadline": "2026-10-07", "done": False}
        ],
        "responsible_party": "IT Security Team"
    })
    if pm:
        r.patch(f"/incidents/{inc_id}/postmortem/finalize")

    r.tick("end")
    print(f"\n✓ Kịch bản 2 hoàn thành! Tổng: {r.elapsed('start','end')}s | Triage: {triage_time}s")
    return {
        "scenario": "credential_compromise",
        "incident_id": inc_id,
        "total_time_s": r.elapsed("start", "end"),
        "triage_time_s": triage_time,
        "status": "completed"
    }