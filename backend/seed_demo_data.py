import sys
import json
from datetime import datetime, timedelta, timezone
import httpx

args = [a for a in sys.argv[1:] if not a.startswith("--")]
FORCE = "--force" in sys.argv
BASE = args[0] if args else "http://localhost:8000"
PWD = "Test@1234"

# Mốc thời gian cho timeline postmortem: khớp với backdate_demo_data.py (sự cố phishing xảy ra 3 ngày trước)
_T1 = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=3)


def _t(minutes):
    return (_T1 + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S")


c = httpx.Client(base_url=BASE, timeout=40.0)
tok = {}
fails = 0


def H(role):
    return {"Authorization": f"Bearer {tok[role]}"}


def call(method, path, role, body=None, files=None, params=None, label=None):
    """Gọi API; lỗi thì in ra và trả None (không dừng script)."""
    global fails
    r = c.request(method, path, headers=H(role), json=body, files=files, params=params)
    if r.status_code >= 400:
        fails += 1
        print(f"  ✗ {label or method + ' ' + path}: {r.status_code} {r.text[:160]}")
        return None
    return r.json()


def step(msg):
    print(f"  · {msg}")


# ─────────────────────────────────────────────── tài khoản
print("Tài khoản")
USERS = [("analyst01", "analyst_soc", "analyst"),
         ("analyst02", "analyst_soc", "analyst2"),
         ("it01", "it_helpdesk", "it"),
         ("stakeholder01", "stakeholder", "stake")]


def account(username, role, headers=None):
    return c.post("/auth/register", json={"username": username, "email": f"{username}@example.com",
                                          "password": PWD, "role": role}, headers=headers or {})


try:
    r = c.post("/auth/login", json={"username": "analyst01", "password": PWD})
    if r.status_code != 200:
        account("analyst01", "analyst_soc")          # tài khoản đầu tiên: khởi tạo hệ thống
        r = c.post("/auth/login", json={"username": "analyst01", "password": PWD})
    r.raise_for_status()
    tok["analyst"] = r.json()["access_token"]
    for u, role, key in USERS[1:]:
        account(u, role, H("analyst"))               # các tài khoản còn lại do Analyst cấp
        r = c.post("/auth/login", json={"username": u, "password": PWD})
        r.raise_for_status()
        tok[key] = r.json()["access_token"]
except Exception as e:                                         # noqa
    print(f"Không kết nối/đăng nhập được: {e}")
    sys.exit(1)
step("đã đăng nhập analyst01 (commander), analyst02, it01, stakeholder01")

existing = call("GET", "/assets/", "analyst") or []
if existing and not FORCE:
    print(f"\nDB đã có {len(existing)} tài sản — dừng để tránh nạp trùng. "
          "Chạy reset_tables.sql trước hoặc thêm --force.")
    sys.exit(1)

# ─────────────────────────────────────────────── tài sản
print("\nTài sản")
ASSETS = [
    ("mail", dict(name="Máy chủ thư điện tử", asset_type="server", criticality="critical",
                  owner="Phòng Công nghệ thông tin", hostname="mail-01", ip_address="10.0.0.10",
                  description="Cổng thư điện tử chính của công ty",
                  data_processed="Thư điện tử nhân viên", dependencies="Active Directory, DNS")),
    ("web", dict(name="Website công ty", asset_type="application", criticality="high",
                 owner="Phòng Truyền thông", hostname="web-01", ip_address="10.0.1.20",
                 description="Website giới thiệu và cổng liên hệ khách hàng",
                 data_processed="Thông tin liên hệ khách hàng", dependencies="Cơ sở dữ liệu khách hàng")),
    ("db", dict(name="Máy chủ cơ sở dữ liệu khách hàng", asset_type="server", criticality="critical",
                owner="Phòng Công nghệ thông tin", hostname="db-01", ip_address="10.0.2.5",
                description="CSDL SQL Server chứa hồ sơ khách hàng",
                data_processed="Hồ sơ khách hàng, hợp đồng", dependencies="Mạng nội bộ VLAN 20")),
    ("m365", dict(name="Tài khoản quản trị Microsoft 365", asset_type="account", criticality="critical",
                  owner="Nguyễn Văn An", description="Tài khoản Global Admin của tenant",
                  data_processed="Toàn bộ dữ liệu M365")),
    ("vpn", dict(name="Hệ thống VPN", asset_type="network", criticality="high",
                 owner="Phòng Công nghệ thông tin", hostname="vpn-gw", ip_address="203.0.113.10",
                 description="Cổng VPN truy cập từ xa cho nhân viên")),
    ("pc", dict(name="Máy trạm phòng Kế toán KT-PC07", asset_type="other", criticality="medium",
                owner="Trần Thị Bình", hostname="KT-PC07", ip_address="10.0.3.37",
                description="Máy trạm của kế toán trưởng",
                data_processed="Chứng từ kế toán")),
    ("hr", dict(name="Ứng dụng quản lý nhân sự", asset_type="application", criticality="medium",
                owner="Phòng Nhân sự", hostname="hr-app", ip_address="10.0.1.40",
                data_processed="Hồ sơ nhân viên, lương")),
    ("fw", dict(name="Tường lửa biên", asset_type="network", criticality="high",
                owner="Phòng Công nghệ thông tin", hostname="fw-edge", ip_address="203.0.113.1",
                description="Tường lửa lớp biên Internet")),
]
A = {}
for key, body in ASSETS:
    r = call("POST", "/assets/", "it", body, label=f"asset {key}")
    if r:
        A[key] = r["id"]
step(f"đã tạo {len(A)}/{len(ASSETS)} tài sản")
if len(A) < len(ASSETS):
    print("Thiếu tài sản — dừng.")
    sys.exit(1)

# ─────────────────────────────────────────────── helpers nghiệp vụ


def new_alert(role, **kw):
    return call("POST", "/alerts/", role, kw, label=f"alert {kw.get('title', '')[:30]}")


def triage(aid, t, sev, conf, sla, note, assignee=None):
    body = {"triage_type": t, "triage_severity": sev, "triage_confidence": conf,
            "triage_sla_hours": sla, "triage_note": note}
    if assignee:
        body["triage_assignee"] = assignee
    return call("PATCH", f"/alerts/{aid}/triage", "analyst", body, label=f"triage {aid}")


_playbooks = {}


def playbook_id(kind):
    if not _playbooks:
        for p in call("GET", "/playbooks/", "analyst", params={"active_only": True}) or []:
            _playbooks[p["incident_type"]] = p["id"]
    return _playbooks.get(kind)


def incident(title, desc, sev, alert_ids, checklist, playbook=None):
    body = {"title": title, "description": desc, "severity": sev,
            "alert_ids": alert_ids, "checklist": checklist}
    if playbook:
        body["playbook_id"] = playbook_id(playbook)
    r = call("POST", "/incidents/", "analyst", body, label=f"incident {title[:30]}")
    return r["id"] if r else None


def work(i, done=0, doing=0, skip_optional=False):
    """Xử lý các công việc theo playbook: done việc đầu tiên xong, doing việc kế tiếp đang làm."""
    tasks = call("GET", f"/incidents/{i}/tasks/", "analyst") or []
    skipped = False
    for k, t in enumerate(tasks):
        who = "it" if t["owner_role"] == "it_helpdesk" else "analyst"
        if k < done:
            if skip_optional and not t["is_required"] and not skipped:
                call("PATCH", f"/incidents/{i}/tasks/{t['id']}", "analyst",
                     {"status": "skipped", "note": "Đã thông báo trực tiếp, không cần gửi thêm"},
                     label=f"task {t['id']} -> skipped")
                skipped = True
            else:
                call("PATCH", f"/incidents/{i}/tasks/{t['id']}", who, {"status": "done"},
                     label=f"task {t['id']} -> done")
        elif k < done + doing:
            call("PATCH", f"/incidents/{i}/tasks/{t['id']}", who, {"status": "in_progress"},
                 label=f"task {t['id']} -> in_progress")


def status(i, s, note=None):
    return call("PATCH", f"/incidents/{i}/status", "analyst",
                {"status": s, "note": note}, label=f"incident {i} -> {s}")


def evidence(i, role, **kw):
    r = call("POST", f"/incidents/{i}/evidences/", role, kw, label=f"evidence {kw['title'][:25]}")
    return r["id"] if r else None


def lock(i, e):
    call("PATCH", f"/incidents/{i}/evidences/{e}/lock", "analyst", label=f"lock evidence {e}")


def impact(i, **kw):
    call("POST", f"/incidents/{i}/impact/", "analyst", kw, label="impact")


def contain(i, action, target, reason, risk, approve=True, execute=True, note="", role="it", verify=True):
    r = call("POST", f"/incidents/{i}/containments/", role,
             {"action_type": action, "target": target, "reason": reason, "risk_level": risk},
             label=f"containment {action}")
    if not r:
        return
    cid = r["id"]
    if approve:
        call("PATCH", f"/incidents/{i}/containments/{cid}/review", "analyst",
             {"approved": True, "review_note": "Đã xem xét, rủi ro chấp nhận được"})
    if approve and execute:
        call("PATCH", f"/incidents/{i}/containments/{cid}/execute", "it",
             {"execution_note": note or "Đã thực hiện theo đề xuất"})
        if verify:
            call("PATCH", f"/incidents/{i}/containments/{cid}/verify", "analyst2",
                 {"verify_note": "Đã kiểm tra: biện pháp ngăn chặn có hiệu lực (mô phỏng)"})


def recover(i, rtype, desc, final="done", confirm=True):
    r = call("POST", f"/incidents/{i}/recovery/", "it",
             {"action_type": rtype, "description": desc}, label=f"recovery {rtype}")
    if not r:
        return
    rid = r["id"]
    if final in ("in_progress", "done"):
        call("PATCH", f"/incidents/{i}/recovery/{rid}/status", "it", {"status": "in_progress"})
    if final == "done":
        call("PATCH", f"/incidents/{i}/recovery/{rid}/status", "it",
             {"status": "done", "note": "Hoàn tất"})
        if confirm:
            call("PATCH", f"/incidents/{i}/recovery/{rid}/confirm", "stake",
                 {"confirm_note": "Chủ hệ thống đã kiểm tra và xác nhận"})


def comm(i, ctype, subject, content, recipients, approve=True, send=True, ack=True):
    r = call("POST", f"/incidents/{i}/communications/", "analyst",
             {"comm_type": ctype, "subject": subject, "content": content,
              "recipients": recipients}, label=f"communication {subject[:25]}")
    if not r:
        return
    k = r["id"]
    if approve:
        call("PATCH", f"/incidents/{i}/communications/{k}/approve", "analyst2")
    if approve and send:
        call("PATCH", f"/incidents/{i}/communications/{k}/send", "analyst")
    if approve and send and ack:
        call("PATCH", f"/incidents/{i}/communications/{k}/acknowledge", "stake")


# ═════════════════════════════════════════════════════ KỊCH BẢN 1: PHISHING (đã đóng)
print("\nKịch bản 1 — Phishing (đã đóng, có postmortem)")
t1 = "Email nghi ngờ phishing mạo danh giám đốc"
d1 = ("Nhân viên nhận email từ ceo-urgent@congty-gia.com kèm tệp HoaDon.exe, "
      "yêu cầu chuyển khoản gấp.")
a1 = new_alert("it", title=t1, description=d1, source="email", severity="high",
               source_ref="MAIL-0001", ioc="ceo-urgent@congty-gia.com,HoaDon.exe",
               affected_asset=A["mail"], raw_data="From: ceo-urgent@congty-gia.com | Subject: Chuyen khoan gap")
if a1:
    tech1 = "T1566.001"
    triage(a1["id"], "phishing", "high", 90, 8, "Mạo danh lãnh đạo, tệp đính kèm thực thi.")
    i1 = incident("Phishing mạo danh giám đốc gửi tệp thực thi",
                  "Email giả mạo lãnh đạo, 2 nhân viên đã mở tệp đính kèm.", "high", [a1["id"]],
                  ["Thu thập header email", "Chặn tên miền người gửi", "Đặt lại mật khẩu người dùng",
                   "Thông báo toàn công ty"], playbook="phishing")
    if i1:
        status(i1, "investigating", "Bắt đầu điều tra")
        e = evidence(i1, "it", title="Header email phishing", evidence_type="email",
                     description="Header đầy đủ của email nghi ngờ", source="Hộp thư nhân viên Lê Văn C",
                     file_hash="9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
                     content="Received: from mail.congty-gia.com (203.0.113.77)")
        if e:
            lock(i1, e)
        impact(i1, ioc_list=["ceo-urgent@congty-gia.com", "HoaDon.exe", "203.0.113.77"],
               affected_assets=[A["mail"]], affected_accounts=["levanc", "phamthid"],
               attck_techniques=[tech1],
               related_events="2 nhân viên mở tệp đính kèm, không phát hiện thực thi thành công",
               summary="Phishing có đính kèm mã độc, phạm vi 2 tài khoản, chưa ghi nhận phát tán.")
        contain(i1, "block_domain", "congty-gia.com", "Tên miền giả mạo đang phát tán email", "medium",
                note="Đã chặn trên bộ lọc thư và DNS (mô phỏng)")
        recover(i1, "reset_credentials", "Đặt lại mật khẩu 2 tài khoản bị ảnh hưởng")
        comm(i1, "stakeholder_notify", "Cập nhật sự cố phishing",
             "Sự cố đã được khống chế. Đề nghị nhân viên không mở email từ địa chỉ lạ.",
             ["stakeholder01"])
        work(i1, done=99, skip_optional=True)
        status(i1, "closed", "Hoàn tất xử lý")
        call("POST", f"/incidents/{i1}/postmortem/", "analyst", {
            "root_cause": "Nhân viên mở tệp đính kèm trong email mạo danh do thiếu đào tạo nhận biết phishing.",
            "timeline": [
                {"time": _t(0), "event": "Nhân viên báo cáo email nghi ngờ", "actor": "it01"},
                {"time": _t(40), "event": "Xác nhận phishing, tạo incident", "actor": "analyst01"},
                {"time": _t(140), "event": "Chặn tên miền, đặt lại mật khẩu", "actor": "it01"},
                {"time": _t(390), "event": "Khôi phục xong, đóng incident", "actor": "analyst01"}],
            "impact": "2 tài khoản bị đặt lại mật khẩu, không có dữ liệu bị đánh cắp.",
            "lessons_learned": "Cần đào tạo nhận biết phishing định kỳ và bật cảnh báo email bên ngoài.",
            "action_items": [
                {"task": "Tổ chức đào tạo nhận biết phishing", "owner": "Phòng CNTT",
                 "deadline": "2026-11-30", "done": False},
                {"task": "Bật gắn thẻ [EXTERNAL] cho email từ bên ngoài", "owner": "Nguyễn Văn An",
                 "deadline": "2026-10-31", "done": True}],
            "responsible_party": "Phòng Công nghệ thông tin"}, label="postmortem 1")
        call("PATCH", f"/incidents/{i1}/postmortem/finalize", "analyst", label="finalize postmortem 1")

# ═════════════════════════════════════════════════════ KỊCH BẢN 2: CREDENTIAL (đang phục hồi)
print("\nKịch bản 2 — Credential compromise (đang phục hồi)")
ids2 = []
for n, ip in enumerate(["203.0.113.45"] * 3, start=1):
    a = new_alert("analyst", title="Nhiều lần đăng nhập VPN thất bại",
                  description=f"Đợt {n}: hơn 50 lần đăng nhập sai vào tài khoản quản trị từ {ip}.",
                  source="ids_ips", severity="high", source_ref=f"IDS-VPN-{n:03d}",
                  ioc=ip, affected_asset=A["vpn"])
    if a:
        triage(a["id"], "credential_compromise", "high", 85, 4,
               "Brute-force liên tục từ cùng một IP.", assignee=None)
        ids2.append(a["id"])
if ids2:
    i2 = incident("Tấn công dò mật khẩu và lộ thông tin đăng nhập VPN",
                  "Brute-force dẫn đến một đăng nhập VPN thành công bất thường.", "critical", ids2,
                  ["Khóa tài khoản bị ảnh hưởng", "Đặt lại thông tin đăng nhập",
                   "Rà soát log VPN 7 ngày", "Bật MFA"], playbook="credential_compromise")
    if i2:
        status(i2, "investigating", "Phát hiện đăng nhập thành công từ IP lạ")
        e = evidence(i2, "analyst", title="Log VPN đăng nhập bất thường", evidence_type="log",
                     description="Trích log VPN 24 giờ", source="vpn-gw",
                     content="2026-10-12 02:14 login OK user=ketoan.binh src=203.0.113.45")
        if e:
            lock(i2, e)
        impact(i2, ioc_list=["203.0.113.45"], affected_assets=[A["vpn"], A["hr"]],
               affected_accounts=["ketoan.binh"], attck_techniques=["T1110", "T1078"],
                related_events="1 đăng nhập thành công lúc 02:14",
               summary="Brute-force VPN dẫn đến chiếm tài khoản kế toán, truy cập ứng dụng nhân sự.")
        contain(i2, "lock_account", "ketoan.binh", "Tài khoản bị chiếm quyền", "high",
                note="Đã khóa tài khoản trên AD (mô phỏng)")
        recover(i2, "reset_credentials", "Đặt lại mật khẩu và thu hồi phiên đăng nhập", final="done")
        recover(i2, "other", "Bật xác thực đa yếu tố cho toàn bộ tài khoản VPN", final="in_progress")
        recover(i2, "patch_vulnerability", "Cập nhật firmware cổng VPN", final="pending")
        comm(i2, "internal_update", "Cập nhật sự cố tài khoản VPN",
             "Đã khóa tài khoản bị ảnh hưởng, đang triển khai MFA.", ["stakeholder01"],
             approve=True, send=False)
        work(i2, done=5, doing=1)

# ═════════════════════════════════════════════════════ KỊCH BẢN 3: MALWARE (đang điều tra)
print("\nKịch bản 3 — Malware (đang điều tra, containment chờ duyệt)")
a3 = new_alert("it", title="Phát hiện mã độc trên máy trạm kế toán",
               description="EDR cảnh báo tiến trình lạ tạo kết nối tới máy chủ điều khiển.",
               source="endpoint", severity="critical", source_ref="EDR-0457",
               ioc="evil-update.example.net,a1b2c3d4e5f60718293a4b5c6d7e8f90", affected_asset=A["pc"])
if a3:
    triage(a3["id"], "malware", "critical", 95, 4, "Beaconing ra ngoài, cần cô lập sớm.")
    i3 = incident("Mã độc beacon từ máy trạm phòng Kế toán",
                  "Máy KT-PC07 kết nối tới tên miền C2 nghi ngờ.", "critical", [a3["id"]],
                  ["Cô lập máy trạm", "Thu thập mẫu mã độc", "Quét toàn bộ máy cùng VLAN"], playbook="malware")
    if i3:
        status(i3, "investigating", "Đang thu thập bằng chứng")
        evidence(i3, "it", title="Mẫu tệp thực thi nghi ngờ", evidence_type="file",
                 description="Tệp trích xuất từ thư mục Temp", source="KT-PC07",
                 file_hash="a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f9")
        evidence(i3, "it", title="Lưu lượng mạng tới C2", evidence_type="network",
                 description="Bắt gói 15 phút", source="fw-edge")
        impact(i3, ioc_list=["evil-update.example.net"], affected_assets=[A["pc"]],
               affected_accounts=["ketoan.tranbinh"], attck_techniques=["T1204.002", "T1071.001"],
                summary="Mã độc trên 1 máy trạm, đang đánh giá khả năng lây lan.")
        contain(i3, "isolate_machine", "KT-PC07", "Ngăn mã độc liên lạc C2 và lây lan", "high",
                approve=False, execute=False)
        work(i3, done=3, doing=1)

# ═════════════════════════════════════════════════════ KỊCH BẢN 4: WEB ATTACK (mới mở)
print("\nKịch bản 4 — Web attack / SQL injection (mới mở)")
a4 = new_alert("analyst", title="Tấn công SQL injection vào website",
               description="WAF chặn nhiều request chứa chuỗi ' OR 1=1-- vào trang liên hệ.",
               source="ids_ips", severity="high", source_ref="WAF-1182",
               ioc="192.0.2.99", affected_asset=A["web"])
if a4:
    triage(a4["id"], "web_attack", "high", 80, 8, "Chuỗi tấn công SQLi điển hình, WAF đã chặn.")
    incident("SQL injection nhắm vào website công ty",
             "Nhiều request SQLi từ cùng một IP, WAF đã chặn nhưng cần rà soát.", "high",
             [a4["id"]], ["Rà soát log ứng dụng", "Kiểm tra dữ liệu có bị truy vấn", "Vá lỗi nhập liệu"],
             playbook="web_attack")

# ═════════════════════════════════════════════════════ CẢNH BÁO LẺ
print("\nCảnh báo lẻ")
new_alert("it", title="Quét cổng từ bên ngoài", description="Nhiều gói SYN tới tường lửa biên.",
          source="ids_ips", severity="low", ioc="198.51.100.7", affected_asset=A["fw"])
new_alert("analyst", title="Đăng nhập ngoài giờ làm việc",
          description="Tài khoản quản trị đăng nhập lúc 23:40.", source="manual",
          severity="medium", affected_asset=A["m365"])
fp = new_alert("it", title="Cảnh báo antivirus trên tệp cài đặt hợp lệ",
               description="Phần mềm kế toán bị cảnh báo nhầm.", source="endpoint", severity="medium")
if fp:
    call("PATCH", f"/alerts/{fp['id']}/false-positive", "analyst")
tr = new_alert("it", title="Thiết bị lạ kết nối mạng nội bộ",
               description="Địa chỉ MAC chưa đăng ký xuất hiện ở VLAN 30.", source="manual",
               severity="medium", ioc="aa:bb:cc:dd:ee:ff")
if tr:
    triage(tr["id"], "unauthorized_device", "medium", 60, 24, "Chờ xác minh với phòng hành chính.")
csv_text = ("title,description,severity,source_ref,ioc\n"
            "Tệp đính kèm đáng ngờ trong email,Tệp .docm chứa macro,medium,MAIL-0102,macro-doc.example.org\n"
            "Truy cập tới tên miền mới đăng ký,Người dùng truy cập tên miền tuổi 2 ngày,low,PROXY-77,new-domain.example.com\n"
            "Tải lên dung lượng lớn bất thường,Máy chủ tệp gửi 4 GB ra ngoài,high,DLP-31,198.51.100.200\n")
r = call("POST", "/alerts/upload/csv", "it",
         files={"file": ("alerts_demo.csv", csv_text.encode("utf-8"), "text/csv")},
         label="upload csv")
if r:
    step(f"đã nhập {len(r)} cảnh báo từ CSV")

# ─────────────────────────────────────────────── tóm tắt
print("\n" + "=" * 64)
alerts = call("GET", "/alerts/", "analyst") or []
incs = call("GET", "/incidents/", "analyst") or []
groups = call("GET", "/alerts/groups/list", "analyst") or []
print(f"Tài sản : {len(A)}")
print(f"Cảnh báo: {len(alerts)}  ({', '.join(f'{k}={sum(1 for x in alerts if x['status']==k)}' for k in sorted({x['status'] for x in alerts}))})")
print(f"Incident: {len(incs)}  ({', '.join(f'#{x['id']}={x['status']}' for x in incs)})")
print(f"Nhóm cảnh báo: {len(groups)}  (lớn nhất: {max([g['alert_count'] for g in groups] or [0])} alert)")
audit = call("GET", "/audit/verify", "analyst") or {}
print(f"Nhật ký kiểm toán: {audit.get('total')} bản ghi, chuỗi băm {'nguyên vẹn' if audit.get('ok') else 'BỊ PHÁ VỠ'}")
dash = c.get("/dashboard/", headers=H("analyst"))
print(f"Dashboard: HTTP {dash.status_code}")
print("=" * 64)
print("HOÀN TẤT" if not fails else f"XONG nhưng có {fails} bước lỗi — xem các dòng ✗ ở trên")
sys.exit(0 if not fails else 1)
