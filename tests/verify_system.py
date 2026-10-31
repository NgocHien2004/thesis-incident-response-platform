import os
import sys
import json
import base64
import platform
import re
import subprocess
from datetime import datetime, timezone

import httpx

_HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_FILE = os.path.join(_HERE, "results", "verify_report.txt")   # cố định trong tests/results, không phụ thuộc thư mục đang đứng
os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
BACKEND_DIR = _HERE
for _d in (_HERE, os.path.join(_HERE, ".."), os.path.join(_HERE, "backend"), os.path.join(_HERE, "..", "backend"),
           os.getcwd(), os.path.join(os.getcwd(), "backend")):
    if os.path.exists(os.path.join(_d, "database.py")):
        BACKEND_DIR = os.path.abspath(_d)
        break
sys.path.insert(0, BACKEND_DIR)

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
BASE = ARGS[0] if ARGS else "http://127.0.0.1:8000"
WITH_FRONTEND = "--frontend" in sys.argv
PWD = "Test@1234"
USERS = {"analyst": "analyst01", "analyst2": "analyst02", "it": "it01", "stake": "stakeholder01"}
PAGE_ROLES = ["analyst", "it", "stake"]

client = httpx.Client(base_url=BASE, timeout=40.0)
lines = []                      # (level, text)  level: OK / WARN / FAIL / INFO / HEAD
tok = {}


def _save_on_crash(exc_type, exc, tb):
    """Lỗi chưa xử lý giữa chừng vẫn để lại báo cáo (phần đã chạy cộng traceback)."""
    import traceback
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"IR Platform — báo cáo kiểm tra {datetime.now():%Y-%m-%d %H:%M:%S}\nKIỂM TRA BỊ NGẮT GIỮA CHỪNG do lỗi chưa xử lý\n\n")
        for lvl, txt in lines:
            f.write(("\n" if lvl == "HEAD" else "") + f"[{lvl}] {txt}\n")
        f.write("\n[FAIL] " + "".join(traceback.format_exception(exc_type, exc, tb)))
    print(f"\nKiểm tra bị ngắt giữa chừng. Phần đã chạy và lỗi được lưu tại {REPORT_FILE}")
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _save_on_crash


def log(level, text):
    lines.append((level, text))
    icon = {"OK": "✓", "WARN": "!", "FAIL": "✗", "INFO": "·", "HEAD": "■"}[level]
    if level == "HEAD":
        print(f"\n{icon} {text}")
    else:
        print(f"  {icon} {text}")


def check(cond, ok_msg, fail_msg, level_fail="FAIL"):
    log("OK" if cond else level_fail, ok_msg if cond else fail_msg)
    return cond


def H(role):
    return {"Authorization": f"Bearer {tok[role]}"}


def get(path, role="analyst", **kw):
    return client.get(path, headers=H(role), **kw)


# ══════════════════════════════════════════════════ A. KẾT NỐI
log("HEAD", "A. Kết nối")
log("INFO", f"Python {platform.python_version()} · {platform.system()} · {datetime.now():%Y-%m-%d %H:%M:%S}")
try:
    r = client.get("/openapi.json")
    n_ops = sum(len(v) for v in r.json()["paths"].values())
    check(r.status_code == 200, f"Backend chạy tại {BASE} ({n_ops} endpoint)", "Backend trả lỗi")
except Exception as e:                                          # noqa
    log("FAIL", f"Không kết nối được backend {BASE}: {e}")
    open(REPORT_FILE, "w", encoding="utf-8").write("Backend không chạy: " + str(e))
    sys.exit(1)

for role, uname in USERS.items():
    r = client.post("/auth/login", json={"username": uname, "password": PWD})
    if r.status_code == 200:
        tok[role] = r.json()["access_token"]
    else:
        log("FAIL", f"Đăng nhập {uname}: HTTP {r.status_code} {r.text[:100]}")
if len(tok) < len(USERS):
    log("FAIL", "Không đủ tài khoản đăng nhập được — dừng. (Chạy seed_demo_data.py trước.)")
    open(REPORT_FILE, "w", encoding="utf-8").write("\n".join(f"[{l}] {t}" for l, t in lines))
    sys.exit(1)
log("OK", "Đăng nhập được 4 tài khoản (analyst01, analyst02, it01, stakeholder01)")

r = get("/ai/health")
try:
    log("OK" if r.status_code == 200 else "WARN",
        f"AI service /ai/health: HTTP {r.status_code} {json.dumps(r.json(), ensure_ascii=False)[:120]}")
except Exception:                                               # noqa
    log("WARN", f"AI service /ai/health: HTTP {r.status_code}")

# ══════════════════════════════════════════════════ B. TOKEN / CORS
log("HEAD", "B. Token và CORS (frontend phụ thuộc vào các mục này)")
try:
    payload = json.loads(base64.urlsafe_b64decode(tok["analyst"].split(".")[1] + "=="))
    check("role" in payload and "sub" in payload,
          f"JWT có claim role='{payload.get('role')}' và sub='{payload.get('sub')}' (AuthContext cần cả hai)",
          f"JWT thiếu claim role/sub: {list(payload)}")
    if "exp" in payload:
        mins = (payload["exp"] - datetime.now(timezone.utc).timestamp()) / 60
        log("INFO", f"Access token còn hiệu lực ~{mins:.0f} phút")
except Exception as e:                                          # noqa
    log("FAIL", f"Không đọc được JWT: {e}")

r = client.options("/alerts/", headers={"Origin": "http://localhost:5173",
                                        "Access-Control-Request-Method": "GET",
                                        "Access-Control-Request-Headers": "authorization"})
check(r.headers.get("access-control-allow-origin") == "http://localhost:5173",
      "CORS cho phép http://localhost:5173",
      f"CORS chưa cho phép localhost:5173 (header={r.headers.get('access-control-allow-origin')})")

# ══════════════════════════════════════════════════ C. TẢI TRANG THEO ROLE
log("HEAD", "C. Tải dữ liệu từng trang theo role (mô phỏng các lời gọi API của frontend)")
incs = get("/incidents/").json()
GLOBAL = ["/dashboard/", "/dashboard/sla", "/alerts/", "/alerts/groups/list", "/assets/", "/incidents/"]
PER_INC = ["", "/alerts", "/evidences/", "/impact/", "/impact/summary", "/containments/",
           "/recovery/", "/recovery/summary", "/communications/", "/communications/log", "/postmortem/", "/timeline"]
bad = []
total = 0
for role in PAGE_ROLES:
    paths = list(GLOBAL)
    for i in incs:
        paths += [f"/incidents/{i['id']}{p}" for p in PER_INC]
    for p in paths:
        total += 1
        r = get(p, role)
        ok = r.status_code == 200 or (p.endswith("/postmortem/") and r.status_code == 404)
        if not ok:
            bad.append(f"{USERS[role]} GET {p} -> {r.status_code} {r.text[:80]}")
check(not bad, f"{total} lời gọi tải trang đều thành công ({len(incs)} incident × 3 role)",
      f"{len(bad)}/{total} lời gọi lỗi")
for b in bad[:15]:
    log("FAIL", "  " + b)

audit_bad = []
for role in USERS:
    want = 200 if role in ("analyst", "analyst2") else 403
    for p in ("/audit/", "/audit/verify"):
        got = get(p, role).status_code
        if got != want:
            audit_bad.append(f"{USERS[role]} GET {p} -> {got} (mong đợi {want})")
check(not audit_bad, "Quyền xem nhật ký kiểm toán đúng: Analyst xem được, IT và Stakeholder bị chặn",
      "Phân quyền nhật ký kiểm toán sai: " + "; ".join(audit_bad))

# ══════════════════════════════════════════════════ D. DASHBOARD
log("HEAD", "D. Số liệu dashboard")
d = get("/dashboard/").json()
m, ic, al = d["metrics"], d["incidents"], d["alerts"]
log("INFO", f"Incident: tổng={ic['total']} mở={ic['open']} đóng={ic['closed']} theo trạng thái={ic['by_status']}")
log("INFO", f"Metrics: {m}")
check(sum(ic["by_status"].values()) == ic["total"], "Tổng incident theo trạng thái khớp tổng",
      "Tổng theo trạng thái KHÔNG khớp tổng incident")
check(sum(al["by_status"].values()) == al["total"], "Tổng alert theo trạng thái khớp tổng",
      "Tổng alert theo trạng thái KHÔNG khớp")
for k in ("mttd_minutes", "mtta_minutes", "mttr_minutes"):
    v = m[k]
    if v is None:
        log("WARN", f"{k} = null (chưa có dữ liệu để tính)")
    else:
        check(v >= 0, f"{k} = {v} phút (không âm)", f"{k} = {v} ÂM — công thức hoặc múi giờ có vấn đề")
for x in get("/dashboard/sla").json():
    if x["status"] != "ok":
        log("INFO", f"SLA {x['status']}: alert #{x['alert_id']} '{x['title'][:35]}' ({x['remaining_minutes']} phút)")

seed_titles = ["Phishing", "Tấn công dò mật khẩu", "Mã độc beacon", "SQL injection"]
is_seed = len(incs) >= 4 and all(i["title"].startswith(t) for i, t in
                                 zip(sorted(incs, key=lambda x: x["id"])[:4], seed_titles))
if is_seed:
    log("INFO", "Nhận ra bộ dữ liệu seed — so sánh với giá trị mong đợi (khi chưa có dữ liệu thêm)")
    exp_status = ["closed", "recovering", "investigating", "open"]
    sorted_i = sorted(incs, key=lambda x: x["id"])[:4]
    check([i["status"] for i in sorted_i] == exp_status,
          f"Trạng thái 4 incident seed đúng: {exp_status}",
          f"Trạng thái incident seed khác mong đợi: {[i['status'] for i in sorted_i]}", "WARN")
    if ic["total"] == 4:
        for key, exp, tol in (("mttd_minutes", 40.0, 1), ("mtta_minutes", 19.5, 1), ("mttr_minutes", 350.0, 1)):
            v = m[key]
            check(v is not None and abs(v - exp) <= tol, f"{key} = {v} (mong đợi ≈ {exp})",
                  f"{key} = {v}, mong đợi ≈ {exp} — chưa chạy backdate_demo_data.py hoặc dashboard.py chưa cập nhật",
                  "WARN")
        check(m["sla_breached_alerts"] == 1, "Vi phạm SLA = 1 như thiết kế",
              f"Vi phạm SLA = {m['sla_breached_alerts']} (mong đợi 1)", "WARN")
        check(m["action_item_completion_pct"] == 50.0, "Action item hoàn thành 50%",
              f"Action item = {m['action_item_completion_pct']} (mong đợi 50.0)", "WARN")
else:
    log("INFO", "Không phải bộ seed nguyên bản (đã có dữ liệu khác) — bỏ qua so sánh giá trị mong đợi")

# ══════════════════════════════════════════════════ E. UNICODE & MÚI GIỜ
log("HEAD", "E. Unicode tiếng Việt và múi giờ")
VI = "Thử nghiệm: Nguyễn Thị Hương – Đặng Quốc Thắng – ăâêôơư ĂÂÊÔƠƯ đĐ ạảãàá ậẩẫầấ ễỗữỳỹ"
t_before = datetime.now(timezone.utc).replace(tzinfo=None)
r = client.post("/assets/", headers=H("analyst"), json={
    "name": VI, "asset_type": "other", "criticality": "low", "owner": "Phòng Công nghệ thông tin",
    "description": VI})
vi_id = None
if r.status_code == 200:
    a = r.json()
    vi_id = a["id"]
    check(a["name"] == VI and a["description"] == VI, "API trả lại đúng 100% chuỗi tiếng Việt vừa lưu",
          f"Chuỗi tiếng Việt BỊ BIẾN DẠNG: gửi '{VI[:40]}…' nhận '{a['name'][:40]}…'")
    # múi giờ: so created_at (server_default) với UTC và giờ máy
    ca = datetime.fromisoformat(a["created_at"].replace("Z", "")).replace(tzinfo=None)
    off_utc = (ca - t_before).total_seconds() / 3600
    local_off = (datetime.now() - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds() / 3600
    log("INFO", f"created_at do DB ghi lệch {off_utc:+.1f} giờ so với UTC (giờ máy lệch UTC {local_off:+.1f})")
    if abs(off_utc) < 0.5:
        log("OK", "created_at đang là UTC — khớp với các mốc thời gian code ghi (triaged_at, detected_at...)")
    else:
        log("FAIL", f"created_at KHÔNG phải UTC (lệch {off_utc:+.1f}h) trong khi triaged_at/detected_at là UTC → "
                    "MTTD/MTTA/SLA trên dữ liệu thật sẽ sai ~" + f"{abs(off_utc):.0f} giờ. Cần sửa server_default.")
else:
    log("FAIL", f"Không tạo được tài sản thử Unicode: {r.status_code} {r.text[:120]}")

# ══════════════════════════════════════════════════ F. TOÀN VẸN DỮ LIỆU (đọc trực tiếp DB)
log("HEAD", "F. Toàn vẹn dữ liệu trong DB")
try:
    from sqlalchemy import text
    from database import SessionLocal, engine
    from app.models.user import User                       # noqa: F401
    from app.models.asset import Asset
    from app.models.alert import Alert
    from app.models.alert_group import AlertGroup           # noqa: F401
    from app.models.incident import Incident
    from app.models.evidence import Evidence, ChainOfCustody
    from app.models.containment import Containment
    from app.models.recovery import RecoveryAction
    from app.models.communication import Communication
    from app.models.postmortem import Postmortem
    import json as _j

    db = SessionLocal()

    # F1. đọc trực tiếp DB: chuỗi Unicode có được lưu đúng không (không qua API)
    if vi_id:
        row = db.get(Asset, vi_id)
        check(row is not None and row.name == VI, "Đọc thẳng từ DB: chuỗi tiếng Việt lưu đúng (cột Unicode)",
              "Đọc thẳng từ DB: chuỗi tiếng Việt SAI — cột chưa phải NVARCHAR")

    # F2. kiểu cột (chỉ SQL Server)
    if engine.dialect.name == "mssql":
        rows = db.execute(text(
            "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE DATA_TYPE IN ('varchar','text','char')")).fetchall()
        # cột Enum (giá trị tiếng Anh cố định) được phép là varchar: lấy từ khai báo của mọi model, không liệt kê tay
        import importlib, pkgutil
        import app.models as _models_pkg
        for _m in pkgutil.iter_modules(_models_pkg.__path__):
            importlib.import_module(f"app.models.{_m.name}")
        from database import Base
        from sqlalchemy import Enum as SAEnum
        enum_cols = {(t.name, c.name) for t in Base.metadata.tables.values() for c in t.columns if isinstance(c.type, SAEnum)}
        suspicious = [f"{t}.{c} ({d})" for t, c, d in rows if (t, c) not in enum_cols]
        check(not suspicious, "Mọi cột chữ tự do đều là NVARCHAR/NTEXT",
              "Cột chữ còn là VARCHAR/TEXT (mất dấu tiếng Việt): " + ", ".join(suspicious[:12]))
        col_row = db.execute(text("SELECT CAST(DATABASEPROPERTYEX(DB_NAME(),'Collation') AS NVARCHAR(100))")).scalar()
        log("INFO", f"Collation của DB: {col_row}")
        tz = db.execute(text("SELECT GETDATE(), GETUTCDATE()")).fetchone()
        log("INFO", f"SQL Server: GETDATE()={tz[0]}  GETUTCDATE()={tz[1]}")
    else:
        log("INFO", f"DB là {engine.dialect.name} — bỏ qua kiểm tra kiểu cột SQL Server")

    A = db.query(Alert).all()
    I = db.query(Incident).all()
    ev_all = db.query(Evidence).all()

    def rep(cond_list, ok, fail, level="FAIL"):
        check(not cond_list, ok, f"{fail}: {cond_list[:8]}{' …' if len(cond_list) > 8 else ''}", level)

    rep([a.id for a in A if a.group_id is None],
        f"Cả {len(A)} alert đều có group_id (chống trùng đã chạy)", "Alert thiếu group_id")
    rep([a.id for a in A if a.incident_id and str(getattr(a.status, 'value', a.status)) not in ("escalated", "closed")],
        "Alert thuộc incident đều ở trạng thái escalated/closed", "Alert có incident nhưng sai trạng thái")
    rep([a.id for a in A if a.triaged_at and a.created_at and a.triaged_at < a.created_at],
        "Mọi alert: triaged_at ≥ created_at", "Alert có triaged_at TRƯỚC created_at (dấu hiệu lệch múi giờ)")
    rep([a.id for a in A if a.triage_sla_deadline and a.triaged_at and a.triage_sla_deadline < a.triaged_at],
        "Hạn SLA luôn sau thời điểm triage", "Hạn SLA trước thời điểm triage")

    bad_det, bad_state = [], []
    for i in I:
        first = min((a.created_at for a in A if a.incident_id == i.id and a.created_at), default=None)
        if first and i.detected_at and i.detected_at < first:
            bad_det.append(i.id)
        st = str(getattr(i.status, "value", i.status))
        if st in ("contained", "recovering", "closed") and not i.contained_at:
            bad_state.append(f"#{i.id}:{st} thiếu contained_at")
        if st == "closed" and (not i.resolved_at or (i.contained_at and i.resolved_at < i.contained_at)):
            bad_state.append(f"#{i.id}: resolved_at thiếu/sai thứ tự")
    rep(bad_det, "Mọi incident: detected_at ≥ alert đầu tiên", "Incident có detected_at TRƯỚC alert đầu tiên")
    rep(bad_state, "Mốc contained/resolved nhất quán với trạng thái incident", "Mốc thời gian incident sai")

    cust = {e.id: db.query(ChainOfCustody).filter(ChainOfCustody.evidence_id == e.id).count() for e in ev_all}
    rep([e for e, n in cust.items() if n == 0], f"Cả {len(ev_all)} bằng chứng đều có nhật ký chain of custody",
        "Bằng chứng không có nhật ký custody")
    rep([e.id for e in ev_all if e.is_locked and cust[e.id] < 2],
        "Bằng chứng đã khóa có ≥2 bản ghi custody (thu thập + khóa)", "Bằng chứng khóa nhưng thiếu bản ghi custody")

    file_evs = [e for e in ev_all if e.storage_key]
    if file_evs:
        from app.core import evidence_store
        bad_files = []
        for e in file_evs:
            res = evidence_store.hash_file(e.storage_key)
            if res is None or res[0] != (e.file_hash or "").lower() or res[1] != e.size_bytes:
                bad_files.append(f"#{e.id} {e.original_filename}")
        rep(bad_files, f"Cả {len(file_evs)} bằng chứng dạng tệp còn trong kho và SHA-256 khớp mã băm ghi nhận",
            "Tệp bằng chứng bị mất hoặc không còn khớp mã băm")
    else:
        log("INFO", "Chưa có bằng chứng dạng tệp để kiểm tra kho lưu trữ")

    C = db.query(Containment).all()
    rep([c.id for c in C if str(getattr(c.status, 'value', c.status)) in ("approved", "executed", "verified")
         and not c.reviewed_by], "Containment đã duyệt/thực hiện đều có người duyệt", "Containment thiếu người duyệt")
    rep([c.id for c in C if str(getattr(c.status, 'value', c.status)) in ("executed", "verified")
         and not c.executed_by], "Containment đã thực hiện đều có người thực hiện", "Containment thiếu người thực hiện")
    R = db.query(RecoveryAction).all()
    rep([r_.id for r_ in R if r_.is_confirmed and str(getattr(r_.status, 'value', r_.status)) != "done"],
        "Recovery đã xác nhận đều ở trạng thái done", "Recovery xác nhận khi chưa done")
    CM = db.query(Communication).all()
    rep([c.id for c in CM if str(getattr(c.status, 'value', c.status)) in ("sent", "acknowledged") and not c.is_approved],
        "Thông báo đã gửi đều đã được phê duyệt", "Thông báo gửi khi chưa duyệt")
    PM = db.query(Postmortem).all()
    rep([p.id for p in PM if p.is_finalized and not _j.loads(p.action_items or "[]")],
        "Postmortem finalized đều có action item", "Postmortem finalized không có action item")
    closed_no_pm = [i.id for i in I if str(getattr(i.status, "value", i.status)) == "closed"
                    and not any(p.incident_id == i.id for p in PM)]
    if closed_no_pm:
        log("WARN", f"Incident đã đóng nhưng chưa có postmortem: {closed_no_pm}")
    from app.models.audit_log import AuditLog
    users = {u.id: u for u in db.query(User).all()}
    role_of = lambda uid: getattr(getattr(users.get(uid), "role", None), "value", None)
    sv = lambda x: str(getattr(x, "value", x))
    inc_by = {i.id: i for i in I}

    rep([c.id for c in C if c.reviewed_by and c.reviewed_by == c.proposed_by],
        "Không containment nào do chính người đề xuất phê duyệt", "Containment tự phê duyệt")
    rep([c.id for c in C if sv(c.status) == "verified" and (not c.verified_by or c.verified_by == c.executed_by)],
        "Containment đã xác minh đều do người khác người thực hiện xác minh", "Containment tự xác minh hoặc thiếu người xác minh")
    rep([c.id for c in C if c.risk_level == "high" and sv(c.status) in ("approved", "executed", "verified")
         and c.reviewed_by != inc_by[c.incident_id].commander_id],
        "Containment rủi ro cao đều do commander của vụ phê duyệt", "Containment rủi ro cao không do commander duyệt")
    rep([x.id for x in R if x.is_confirmed and role_of(x.confirmed_by) != "stakeholder"],
        "Mọi recovery đều do chủ hệ thống (stakeholder) xác nhận", "Recovery được xác nhận bởi người không phải chủ hệ thống")
    rep([x.id for x in CM if x.approved_by and x.approved_by == x.sent_by],
        "Không thông báo nào do chính người soạn phê duyệt", "Thông báo tự phê duyệt")
    rep([i.id for i in I if not i.commander_id or role_of(i.commander_id) != "analyst_soc"],
        "Mọi incident đều có commander là tài khoản Analyst", "Incident thiếu commander hợp lệ")

    bad_close = []
    for i in I:
        if sv(i.status) != "closed":
            continue
        cs = [c for c in C if c.incident_id == i.id]
        rs = [x for x in R if x.incident_id == i.id]
        if any(sv(c.status) in ("proposed", "approved", "executed") for c in cs):
            bad_close.append(f"#{i.id}: còn containment chưa xử lý hoặc chưa xác minh")
        if not any(x.is_confirmed for x in rs):
            bad_close.append(f"#{i.id}: chưa có recovery nào được chủ hệ thống xác nhận")
    rep(bad_close, "Mọi incident đã đóng đều thỏa tiêu chí đóng", "Incident đóng khi chưa đủ tiêu chí")

    logged = {(a.entity_type, a.entity_id, a.action) for a in db.query(AuditLog).all()}
    rep([i.id for i in I if ("incident", i.id, "incident.created") not in logged],
        "Mọi incident đều có bản ghi tạo trong nhật ký kiểm toán", "Incident không có trong nhật ký kiểm toán")
    rep([i.id for i in I if sv(i.status) == "closed" and ("incident", i.id, "incident.closed") not in logged],
        "Mọi incident đã đóng đều có bản ghi đóng trong nhật ký", "Incident đóng nhưng không có bản ghi nhật ký")
    chain = get("/audit/verify", "analyst").json()
    check(chain.get("ok") is True, f"Chuỗi băm nhật ký kiểm toán nguyên vẹn ({chain.get('total')} bản ghi)",
          f"Chuỗi băm nhật ký BỊ PHÁ VỠ tại bản ghi #{chain.get('first_bad_id')}")
    counts = {}
    for uu in users.values():
        counts[role_of(uu.id)] = counts.get(role_of(uu.id), 0) + 1
    log("INFO", f"Tài khoản theo vai trò: {counts}")
    log("INFO", f"Số lượng bản ghi: alert={len(A)} incident={len(I)} evidence={len(ev_all)} "
                f"containment={len(C)} recovery={len(R)} communication={len(CM)} postmortem={len(PM)}")
    db.close()
except Exception as e:                                          # noqa
    log("FAIL", f"Không đọc được DB trực tiếp: {type(e).__name__}: {str(e)[:200]}")

# dọn tài sản thử
if vi_id:
    r = client.delete(f"/assets/{vi_id}", headers=H("analyst"))
    log("INFO", f"Đã xóa tài sản thử Unicode (HTTP {r.status_code})")

# ══════════════════════════════════════════════════ G. FRONTEND (tùy chọn)
log("HEAD", "G. Frontend")
try:
    r = httpx.get("http://localhost:5173", timeout=5)
    log("OK" if r.status_code == 200 else "WARN", f"Dev server localhost:5173: HTTP {r.status_code}")
except Exception:                                               # noqa
    log("INFO", "Dev server localhost:5173 chưa chạy (không bắt buộc)")

if WITH_FRONTEND:
    fe = os.path.join(os.path.dirname(BACKEND_DIR), "frontend")
    if not os.path.isdir(os.path.join(fe, "node_modules")):
        log("WARN", f"Chưa có {fe}\\node_modules — chạy 'npm install' trong thư mục frontend trước")
    else:
        log("INFO", "Đang chạy 'npm run build' (xuất ra thư mục tạm, không ghi đè dist/)...")
        out_dir = os.path.join(os.environ.get("TEMP", "/tmp"), "ir_fe_build_check")
        try:
            p = subprocess.run(f'npm run build -- --outDir "{out_dir}" --emptyOutDir', cwd=fe, shell=True,
                               capture_output=True, text=True, timeout=400, encoding="utf-8", errors="replace")
            tail = re.sub(r"\x1b\[[0-9;]*m", "", "\n".join((p.stdout + p.stderr).strip().splitlines()[-12:]))   # bỏ mã màu ANSI của npm
            check(p.returncode == 0, "Frontend build thành công (mọi trang compile được)",
                  "Frontend build THẤT BẠI:\n" + tail)
            if p.returncode == 0:
                last = [ln for ln in tail.splitlines() if ln.strip()]
                if last:
                    log("INFO", last[-1].strip())
        except Exception as e:                                  # noqa
            log("FAIL", f"Không chạy được build: {e}")
else:
    log("INFO", "Bỏ qua kiểm tra build (thêm --frontend để bật)")

# ══════════════════════════════════════════════════ TỔNG KẾT
n_ok = sum(1 for l, _ in lines if l == "OK")
n_warn = sum(1 for l, _ in lines if l == "WARN")
n_fail = sum(1 for l, _ in lines if l == "FAIL")
summary = f"TỔNG KẾT: {n_ok} đạt · {n_warn} cảnh báo · {n_fail} lỗi"
print("\n" + "=" * 72 + f"\n{summary}\n" + "=" * 72)
with open(REPORT_FILE, "w", encoding="utf-8") as f:
    f.write(f"IR Platform — báo cáo kiểm tra {datetime.now():%Y-%m-%d %H:%M:%S}\n{summary}\n\n")
    for lvl, txt in lines:
        f.write(("\n" if lvl == "HEAD" else "") + f"[{lvl}] {txt}\n")
print(f"Báo cáo lưu tại {REPORT_FILE}")
sys.exit(1 if n_fail else 0)