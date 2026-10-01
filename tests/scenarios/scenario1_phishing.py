from tests.scenarios.base import ScenarioRunner
import time

def run(analyst_token=None):
    print("\n" + "="*60)
    print("KỊCH BẢN 1 — Phishing Email")
    print("="*60)

    r = ScenarioRunner("analyst01", "Test@1234").login()
    r_it = ScenarioRunner("it01", "Test@1234").login()
    r_st = ScenarioRunner("stakeholder01", "Test@1234").login()

    r.tick("start")

    # 1. Tạo alert phishing
    print("\n[1] Tạo alert phishing...")
    alert = r_it.post("/alerts/", {
        "title": "Suspicious phishing email detected",
        "description": "Employee received email from ceo-urgent@company-fake.com with malicious attachment Invoice.exe",
        "source": "email",
        "severity": "high",
        "ioc": "ceo-urgent@company-fake.com,Invoice.exe",
        "affected_asset": 1
    })
    if not alert: return None
    alert_id = alert["id"]
    r.tick("alert_created")
    print(f"  Alert #{alert_id} tạo thành công")

    # 2. AI suggest
    print("\n[2] AI đề xuất ATT&CK...")
    suggest = r.post("/ai/alert/suggest", {
        "title": alert["title"],
        "description": alert["description"],
        "ioc": alert["ioc"]
    })
    if suggest:
        print(f"  AI severity: {suggest['severity_suggestion']}")
        print(f"  Top technique: {suggest['attck_techniques'][0]['id']} — {suggest['attck_techniques'][0]['name']}")

    # 3. Triage
    print("\n[3] Triage alert...")
    r.tick("triage_start")
    triage = r.patch(f"/alerts/{alert_id}/triage", {
        "triage_type": "phishing",
        "triage_severity": "high",
        "triage_confidence": 90,
        "triage_assignee": 1,
        "triage_sla_hours": 4,
        "triage_note": "Xác nhận email giả mạo CEO, file đính kèm chứa malware"
    })
    r.tick("triage_done")
    if triage:
        print(f"  Triage xong — status: {triage['status']}")
    triage_time = r.elapsed("triage_start", "triage_done")

    # 4. Tạo incident
    print("\n[4] Tạo incident...")
    incident = r.post("/incidents/", {
        "title": "Phishing campaign targeting finance department",
        "description": "CEO impersonation phishing với malicious attachment",
        "severity": "high",
        "commander_id": 1,
        "alert_ids": [alert_id]
    })
    if not incident: return None
    inc_id = incident["id"]
    print(f"  Incident #{inc_id} tạo thành công")

    # 5. Thu thập bằng chứng
    print("\n[5] Thu thập bằng chứng...")
    r_it.post(f"/incidents/{inc_id}/evidences/", {
        "title": "Email header phishing",
        "evidence_type": "email",
        "source": "Mail server logs",
        "content": "From: ceo-urgent@company-fake.com\nTo: finance@company.com\nSubject: URGENT: Wire Transfer\nAttachment: Invoice.exe (SHA256: abc123)"
    })

    # 6. Phân tích phạm vi
    print("\n[6] Phân tích phạm vi...")
    r.post(f"/incidents/{inc_id}/impact/", {
        "ioc_list": ["ceo-urgent@company-fake.com", "Invoice.exe"],
        "affected_assets": [1],
        "affected_accounts": ["finance01", "cfo"],
        "attck_techniques": ["T1566.001", "T1204.002"],
        "attck_version": "14.1",
        "summary": "Phishing giả mạo CEO nhắm vào bộ phận tài chính, kỹ thuật T1566.001"
    })

    # 7. Containment
    print("\n[7] Containment...")
    r.patch(f"/incidents/{inc_id}/status", {"status": "investigating"})
    cont = r_it.post(f"/incidents/{inc_id}/containments/", {
        "action_type": "block_domain",
        "target": "company-fake.com",
        "reason": "Domain giả mạo dùng trong phishing campaign",
        "risk_level": "low"
    })
    if cont:
        r.patch(f"/incidents/{inc_id}/containments/{cont['id']}/review", {
            "approved": True, "review_note": "Xác nhận domain độc hại"
        })
        r_it.patch(f"/incidents/{inc_id}/containments/{cont['id']}/execute", {
            "execution_note": "Block domain company-fake.com trên email gateway (mô phỏng)"
        })

    # 8. Recovery
    print("\n[8] Recovery...")
    rec = r_it.post(f"/incidents/{inc_id}/recovery/", {
        "action_type": "reset_credentials",
        "description": "Reset mật khẩu các tài khoản nhận email phishing",
        "assigned_to": 2
    })
    if rec:
        r_it.patch(f"/incidents/{inc_id}/recovery/{rec['id']}/status", {
            "status": "done",
            "note": "Đã reset password finance01 và cfo"
        })
        r_st.patch(f"/incidents/{inc_id}/recovery/{rec['id']}/confirm", {
            "confirm_note": "Xác nhận hệ thống email an toàn trở lại"
        })

    # 9. Postmortem
    print("\n[9] Postmortem...")
    pm = r.post(f"/incidents/{inc_id}/postmortem/", {
        "root_cause": "Thiếu email authentication (DMARC/SPF) cho phép giả mạo domain",
        "timeline": [
            {"time": "08:30", "event": "Nhân viên nhận email phishing", "actor": "attacker"},
            {"time": "09:00", "event": "IDS phát hiện và tạo alert", "actor": "system"},
            {"time": "09:15", "event": "Analyst triage và tạo incident", "actor": "analyst01"},
            {"time": "10:00", "event": "Block domain và reset credentials", "actor": "it01"},
        ],
        "impact": "2 tài khoản tài chính bị nhắm mục tiêu, không có thiệt hại thực tế",
        "lessons_learned": "Cần triển khai DMARC/SPF/DKIM và training nhân viên",
        "action_items": [
            {"task": "Triển khai DMARC cho domain công ty", "owner": "it01", "deadline": "2026-10-10", "done": False},
            {"task": "Security awareness training cho nhân viên tài chính", "owner": "analyst01", "deadline": "2026-10-15", "done": False}
        ],
        "responsible_party": "IT Security Team"
    })
    if pm:
        r.patch(f"/incidents/{inc_id}/postmortem/finalize")

    r.tick("end")
    total_time = r.elapsed("start", "end")

    print(f"\n✓ Kịch bản 1 hoàn thành!")
    print(f"  Tổng thời gian: {total_time}s")
    print(f"  Thời gian triage: {triage_time}s")
    return {
        "scenario": "phishing",
        "incident_id": inc_id,
        "total_time_s": total_time,
        "triage_time_s": triage_time,
        "status": "completed"
    }