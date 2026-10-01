from tests.scenarios.base import ScenarioRunner

def run():
    print("\n" + "="*60)
    print("KỊCH BẢN 4 — Web Attack (SQL Injection)")
    print("="*60)

    r    = ScenarioRunner("analyst01", "Test@1234").login()
    r_it = ScenarioRunner("it01", "Test@1234").login()
    r_st = ScenarioRunner("stakeholder01", "Test@1234").login()
    r.tick("start")

    alert = r_it.post("/alerts/", {
        "title": "SQL Injection attack on web application",
        "description": "WAF detected SQL injection patterns in POST /login, 500+ attempts in 10 minutes",
        "source": "ids_ips",
        "severity": "high",
        "ioc": "203.0.113.42,sqlmap/1.7",
        "affected_asset": 1
    })
    if not alert: return None
    alert_id = alert["id"]

    r.tick("triage_start")
    r.patch(f"/alerts/{alert_id}/triage", {
        "triage_type": "web_attack",
        "triage_severity": "high",
        "triage_confidence": 88,
        "triage_assignee": 1,
        "triage_sla_hours": 4,
        "triage_note": "SQLMap automated scan, nhắm vào login endpoint"
    })
    r.tick("triage_done")

    incident = r.post("/incidents/", {
        "title": "SQL Injection attack on web application",
        "severity": "high",
        "commander_id": 1,
        "alert_ids": [alert_id]
    })
    if not incident: return None
    inc_id = incident["id"]

    r_it.post(f"/incidents/{inc_id}/evidences/", {
        "title": "WAF access log",
        "evidence_type": "log",
        "source": "WAF / Nginx",
        "content": "203.0.113.42 - POST /login - 'OR 1=1-- - 403\n203.0.113.42 - POST /login - UNION SELECT - 403"
    })
    r.post(f"/incidents/{inc_id}/impact/", {
        "ioc_list": ["203.0.113.42", "sqlmap/1.7"],
        "affected_assets": [1],
        "affected_accounts": [],
        "attck_techniques": ["T1190", "T1059.007"],
        "attck_version": "14.1",
        "summary": "SQL Injection T1190 khai thác web app, chưa có dấu hiệu thành công"
    })

    r.patch(f"/incidents/{inc_id}/status", {"status": "investigating"})
    cont = r_it.post(f"/incidents/{inc_id}/containments/", {
        "action_type": "block_ip",
        "target": "203.0.113.42",
        "reason": "IP đang thực hiện automated SQL injection scan",
        "risk_level": "low"
    })
    if cont:
        r.patch(f"/incidents/{inc_id}/containments/{cont['id']}/review", {
            "approved": True, "review_note": "Block IP scan"
        })
        r_it.patch(f"/incidents/{inc_id}/containments/{cont['id']}/execute", {
            "execution_note": "Block 203.0.113.42 trên WAF và firewall (mô phỏng)"
        })

    rec = r_it.post(f"/incidents/{inc_id}/recovery/", {
        "action_type": "patch_vulnerability",
        "description": "Review và patch SQL injection vulnerability trong login endpoint",
        "assigned_to": 2
    })
    if rec:
        r_it.patch(f"/incidents/{inc_id}/recovery/{rec['id']}/status", {
            "status": "done",
            "note": "Dùng parameterized query, đã test lại không còn lỗ hổng"
        })
        r_st.patch(f"/incidents/{inc_id}/recovery/{rec['id']}/confirm", {
            "confirm_note": "Web app hoạt động bình thường, WAF không còn phát hiện tấn công"
        })

    pm = r.post(f"/incidents/{inc_id}/postmortem/", {
        "root_cause": "Login endpoint dùng string concatenation thay vì parameterized query",
        "timeline": [
            {"time": "10:00", "event": "SQLMap bắt đầu scan từ 203.0.113.42", "actor": "attacker"},
            {"time": "10:05", "event": "WAF phát hiện và block request", "actor": "waf"},
            {"time": "10:10", "event": "IDS tạo alert, analyst triage", "actor": "analyst01"},
            {"time": "10:30", "event": "Block IP, patch code", "actor": "it01"},
        ],
        "impact": "Không có dữ liệu bị lấy, WAF block thành công 100% request",
        "lessons_learned": "Code review bắt buộc kiểm tra SQL injection, dùng ORM hoặc parameterized query",
        "action_items": [
            {"task": "Security code review toàn bộ web application", "owner": "analyst01", "deadline": "2026-10-20", "done": False},
            {"task": "Triển khai SAST trong CI/CD pipeline", "owner": "it01", "deadline": "2026-10-25", "done": False}
        ],
        "responsible_party": "Development Team"
    })
    if pm:
        r.patch(f"/incidents/{inc_id}/postmortem/finalize")

    r.tick("end")
    print(f"\n✓ Kịch bản 4 hoàn thành! Tổng: {r.elapsed('start','end')}s | Triage: {r.elapsed('triage_start','triage_done')}s")
    return {
        "scenario": "web_attack",
        "incident_id": inc_id,
        "total_time_s": r.elapsed("start", "end"),
        "triage_time_s": r.elapsed("triage_start", "triage_done"),
        "status": "completed"
    }