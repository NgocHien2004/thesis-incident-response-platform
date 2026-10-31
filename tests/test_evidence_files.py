import sys, os, json, hashlib, glob
import requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.scenarios.base import login_all, new_incident, BASE_URL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.getenv("EVIDENCE_STORAGE_DIR") or os.path.join(ROOT, "backend", "evidence_store")
MAX_MB = int(os.getenv("EVIDENCE_MAX_MB", "20"))

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


def expect(label, resp, *codes):
    check(label, resp.status_code in codes, f"HTTP {resp.status_code}, mong đợi {'/'.join(map(str, codes))}")
    return resp


def sha(b):
    return hashlib.sha256(b).hexdigest()


def run():
    print("╔══════════════════════════════════════════════╗")
    print("║  KIỂM THỬ BẰNG CHỨNG DẠNG TỆP (BP10.4)      ║")
    print("╚══════════════════════════════════════════════╝")

    u = login_all()
    A, A2, IT, ST = u["analyst"], u["analyst2"], u["it"], u["st"]
    inc = new_incident(u, "Kiểm thử bằng chứng dạng tệp")
    other = new_incident(u, "Incident khác cho bằng chứng")
    base = f"{BASE_URL}/incidents/{inc}/evidences"
    print(f"\n  Dùng incident #{inc} và #{other} (tạo riêng cho bài kiểm thử)\n")

    def upload(who, data, filename="mau.bin", incident=inc, **form):
        fields = {"title": "Tệp kiểm thử", "evidence_type": "file", "source": "máy trạm WS-01"}
        fields.update(form)
        fields = {k: v for k, v in fields.items() if v is not None}
        return requests.post(f"{BASE_URL}/incidents/{incident}/evidences/upload", headers=who.headers(),
                             data=fields, files={"file": (filename, data, "application/x-test")})

    def get(who, path, **kw):
        return requests.get(f"{base}{path}", headers=who.headers(), **kw)

    def post(who, path, **kw):
        return requests.post(f"{base}{path}", headers=who.headers(), **kw)

    def custody(ev_id):
        return get(A, f"/{ev_id}/custody").json()

    def stored_files(incident=inc):
        return sorted(glob.glob(os.path.join(STORE, str(incident), "*")))

    # ── 1 ──────────────────────────────────────────────
    print("── 1. Tải tệp lên: băm trên byte, tên an toàn ──")
    data = bytes(range(256)) * 40 + b"\x00\xff\xfe"      # nhị phân, có byte 0x00 và không phải UTF-8
    r = upload(IT, data, filename="../..\\Báo cáo\x07 đính kèm?.bin")
    expect("IT tải tệp lên thành công", r, 200)
    ev = r.json() if r.status_code == 200 else {}
    ev_id = ev.get("id")
    if not ev_id:
        return False
    check("SHA-256 tính đúng trên byte của tệp", ev.get("file_hash") == sha(data))
    check("Ghi đúng kích thước", ev.get("size_bytes") == len(data), f"{ev.get('size_bytes')} byte")
    check("Tên tệp chỉ giữ phần tên, bỏ đường dẫn và ký tự điều khiển", ev.get("original_filename") == "Báo cáo đính kèm?.bin",
          repr(ev.get("original_filename")))
    check("Đánh dấu có tệp, không có nội dung chữ", ev.get("has_file") is True and ev.get("content") is None)
    check("Không lộ khóa lưu trữ nội bộ ra API", "storage_key" not in ev)
    check("Bằng chứng mới chưa khóa", ev.get("is_locked") is False)
    files = stored_files()
    on_disk_ok = len(files) == 1
    if on_disk_ok:
        with open(files[0], "rb") as f:
            check("Tệp trong kho giống hệt byte đã tải lên", f.read() == data)
        check("Tên tệp trong kho do server sinh, không dùng tên người dùng", "Báo" not in os.path.basename(files[0]))
    else:
        print(f"  · BỎ QUA kiểm tra tệp trên đĩa: không thấy kho tại {STORE}")
    cust = custody(ev_id)
    check("Chain of custody có 'collected' kèm mã băm", cust and cust[0]["action"] == "collected" and sha(data) in cust[0]["note"])

    # ── 2 ──────────────────────────────────────────────
    print("\n── 2. Từ chối đầu vào không hợp lệ ──")
    before = len(get(A, "/").json())
    files_before = stored_files()
    expect("Tệp rỗng bị từ chối", upload(IT, b""), 400)
    expect("Thiếu tiêu đề bị từ chối", upload(IT, b"abc", title=""), 422)
    big = b"\0" * (MAX_MB * 1024 * 1024 + 1)
    expect(f"Tệp vượt {MAX_MB} MB bị từ chối", upload(IT, big), 413)
    del big
    check("Tệp bị từ chối không tạo bằng chứng", len(get(A, "/").json()) == before)
    check("Tệp bị từ chối không để lại rác trong kho", stored_files() == files_before or not on_disk_ok)
    expect("Stakeholder không được tải tệp lên", upload(ST, b"abc"), 403)
    expect("Không đăng nhập không tải tệp lên được", requests.post(f"{base}/upload", data={"title": "x", "evidence_type": "file"},
           files={"file": ("a.bin", b"abc")}), 401, 403)

    # ── 3 ──────────────────────────────────────────────
    print("\n── 3. Bản sao làm việc: kiểm tra trước khi cấp, ghi chain of custody ──")
    d = get(IT, f"/{ev_id}/download")
    expect("IT tải bản sao làm việc", d, 200)
    check("Nội dung bản sao giống hệt tệp gốc", d.content == data and sha(d.content) == ev["file_hash"])
    disp = d.headers.get("content-disposition", "")
    check("Phát dạng tải về (attachment), không hiển thị trong trình duyệt", disp.lower().startswith("attachment"), disp)
    check("Kiểu nội dung trung tính và chặn đoán kiểu", d.headers.get("content-type", "").startswith("application/octet-stream")
          and d.headers.get("x-content-type-options") == "nosniff")
    cust = custody(ev_id)
    issued = [c for c in cust if c["action"] == "working_copy_issued"]
    check("Chain of custody ghi 'working_copy_issued' kèm mã băm", len(issued) == 1 and ev["file_hash"] in issued[0]["note"])
    expect("Analyst cũng tải được bản sao", get(A, f"/{ev_id}/download"), 200)
    expect("Stakeholder không tải được tệp bằng chứng", get(ST, f"/{ev_id}/download"), 403)
    expect("Bằng chứng của incident khác trả 404", requests.get(f"{BASE_URL}/incidents/{other}/evidences/{ev_id}/download",
           headers=A.headers()), 404)
    expect("Bằng chứng không tồn tại trả 404", get(A, "/999999/download"), 404)
    lst = get(ST, "/")
    check("Stakeholder vẫn xem được danh sách (thấy có tệp, không thấy khóa lưu trữ)",
          lst.status_code == 200 and any(e.get("has_file") for e in lst.json()) and "storage_key" not in lst.text)

    # ── 4 ──────────────────────────────────────────────
    print("\n── 4. Kiểm tra toàn vẹn ──")
    v = post(IT, f"/{ev_id}/verify")
    expect("Kiểm tra toàn vẹn tệp nguyên vẹn", v, 200)
    vj = v.json()
    check("Kết quả đạt, đã băm lại tệp", vj.get("ok") is True and vj.get("checked") == "file" and vj.get("actual") == vj.get("expected") == sha(data))
    check("Chain of custody ghi 'verified'", "verified" in [c["action"] for c in custody(ev_id)])
    expect("Stakeholder không được chạy kiểm tra toàn vẹn", post(ST, f"/{ev_id}/verify"), 403)

    text = "SSH Failed password for root from 1.2.3.4 — kiểm thử"
    t_ev = requests.post(base + "/", headers=IT.headers(), json={"title": "Log chữ", "evidence_type": "log", "content": text}).json()
    tv = post(IT, f"/{t_ev['id']}/verify").json()
    check("Bằng chứng dạng chữ cũng kiểm tra được (băm lại nội dung)", tv.get("ok") is True and tv.get("checked") == "content")
    bad = requests.post(base + "/", headers=IT.headers(),
                        json={"title": "Hash khai sai", "evidence_type": "log", "content": text, "file_hash": "0" * 64}).json()
    bv = post(IT, f"/{bad['id']}/verify").json()
    check("Mã băm do client khai sai bị phát hiện", bv.get("ok") is False)
    check("Phát hiện sai được ghi 'integrity_failed'", "integrity_failed" in [c["action"] for c in custody(bad["id"])])
    h_ev = requests.post(base + "/", headers=IT.headers(),
                         json={"title": "Chỉ có hash", "evidence_type": "hash", "file_hash": "a" * 64}).json()
    expect("Bằng chứng không có dữ liệu để băm bị từ chối kiểm tra", post(IT, f"/{h_ev['id']}/verify"), 400)
    expect("Bằng chứng chữ không có tệp thì tải về trả 404", get(IT, f"/{t_ev['id']}/download"), 404)

    trav = requests.post(base + "/", headers=IT.headers(),
                         json={"title": "Đường dẫn giả", "evidence_type": "file", "file_path": "../../../../etc/passwd",
                               "content": "x"}).json()
    expect("file_path do client khai không bao giờ được dùng để đọc tệp", get(IT, f"/{trav['id']}/download"), 404)

    # ── 5 ──────────────────────────────────────────────
    print("\n── 5. Phát hiện tệp gốc bị sửa hoặc mất ──")
    if not on_disk_ok:
        print("  · BỎ QUA mục này: kiểm thử không thấy kho tệp của backend trên đĩa")
    else:
        data2 = b"nguyen ven\n" * 500
        ev2 = upload(IT, data2, filename="log.txt", title="Tệp sẽ bị sửa").json()
        p2 = [f for f in stored_files() if f not in files][0]
        os.chmod(p2, 0o666)
        with open(p2, "ab") as f:
            f.write(b"X")
        n_issued = len([c for c in custody(ev2["id"]) if c["action"] == "working_copy_issued"])
        vt = post(IT, f"/{ev2['id']}/verify")
        check("Tệp bị sửa 1 byte: kiểm tra toàn vẹn báo không khớp", vt.status_code == 200 and vt.json().get("ok") is False
              and vt.json().get("actual") != vt.json().get("expected"))
        c2 = custody(ev2["id"])
        fail_notes = [c["note"] for c in c2 if c["action"] == "integrity_failed"]
        check("Chain of custody ghi 'integrity_failed' kèm cả hai mã băm",
              len(fail_notes) == 1 and sha(data2) in fail_notes[0] and sha(data2 + b"X") in fail_notes[0])
        expect("Không cấp bản sao làm việc của tệp đã bị sửa", get(IT, f"/{ev2['id']}/download"), 409)
        check("Không ghi 'working_copy_issued' khi từ chối",
              len([c for c in custody(ev2["id"]) if c["action"] == "working_copy_issued"]) == n_issued)
        expect("Không khóa được bằng chứng đã bị sửa", requests.patch(f"{base}/{ev2['id']}/lock", headers=A.headers()), 409)
        check("Bằng chứng vẫn chưa khóa sau lần khóa bị từ chối",
              [e for e in get(A, "/").json() if e["id"] == ev2["id"]][0]["is_locked"] is False)
        os.remove(p2)
        vm = post(IT, f"/{ev2['id']}/verify")
        check("Tệp bị mất khỏi kho: báo không khớp, không lỗi máy chủ", vm.status_code == 200 and vm.json().get("ok") is False
              and vm.json().get("actual") is None)
        expect("Tệp bị mất thì không cấp bản sao", get(IT, f"/{ev2['id']}/download"), 409)
        # trả kho về trạng thái nhất quán để verify_system không báo lỗi sau khi test chạy
        with open(p2, "wb") as f:
            f.write(data2)
        os.chmod(p2, 0o444)
        vr = post(IT, f"/{ev2['id']}/verify")
        check("Khôi phục đúng byte gốc thì kiểm tra lại đạt (so theo nội dung)", vr.status_code == 200 and vr.json().get("ok") is True)
        expect("Sau khi khôi phục lại cấp được bản sao làm việc", get(IT, f"/{ev2['id']}/download"), 200)

    # ── 6 ──────────────────────────────────────────────
    print("\n── 6. Khóa bằng chứng dạng tệp ──")
    data3 = b"bang chung can khoa\n" * 100
    ev3 = upload(A, data3, filename="khoa.log", title="Tệp sẽ khóa").json()
    lk = requests.patch(f"{base}/{ev3['id']}/lock", headers=A.headers())
    expect("Khóa bằng chứng dạng tệp nguyên vẹn", lk, 200)
    lock_note = [c for c in custody(ev3["id"]) if c["action"] == "locked"][0]["note"]
    check("Ghi chú khóa nêu mã băm đã kiểm tra khớp", sha(data3) in lock_note)
    expect("Không khóa lần hai", requests.patch(f"{base}/{ev3['id']}/lock", headers=A.headers()), 400)
    check("Sau khi khóa vẫn tải bản sao và kiểm tra được",
          get(A, f"/{ev3['id']}/download").status_code == 200 and post(A, f"/{ev3['id']}/verify").json().get("ok") is True)

    # ── 7 ──────────────────────────────────────────────
    print("\n── 7. Incident đã đóng không nhận thêm bằng chứng ──")
    closed = new_incident(u, "Incident đóng để thử bằng chứng")
    cb = {"action_type": "block_ip", "target": "9.9.9.9", "reason": "test", "risk_level": "low"}
    cid = IT.raw("POST", f"/incidents/{closed}/containments/", cb).json()["id"]
    A2.raw("PATCH", f"/incidents/{closed}/containments/{cid}/review", {"approved": True})
    IT.raw("PATCH", f"/incidents/{closed}/containments/{cid}/execute", {"execution_note": "mô phỏng"})
    A2.raw("PATCH", f"/incidents/{closed}/containments/{cid}/verify", {"verify_note": "ok"})
    rid = IT.raw("POST", f"/incidents/{closed}/recovery/", {"action_type": "reset_credentials", "description": "test"}).json()["id"]
    IT.raw("PATCH", f"/incidents/{closed}/recovery/{rid}/status", {"status": "done"})
    ST.raw("PATCH", f"/incidents/{closed}/recovery/{rid}/confirm", {"confirm_note": "ok"})
    A.raw("PATCH", f"/incidents/{closed}/status", {"status": "closed"})
    n_files = len(stored_files(closed))
    expect("Tải tệp vào incident đã đóng bị từ chối", upload(IT, b"abc", incident=closed), 409)
    check("Bị từ chối thì không để lại tệp trong kho", len(stored_files(closed)) == n_files)

    # ── 8 ──────────────────────────────────────────────
    print("\n── 8. Nhật ký kiểm toán ──")
    tl = A.get(f"/incidents/{inc}/timeline") or []
    check("Timeline có sự kiện thu thập bằng chứng", "Thu thập bằng chứng" in [t["label"] for t in tl])
    check("Chuỗi băm nhật ký kiểm toán nguyên vẹn", (A.get("/audit/verify") or {}).get("ok") is True)

    print(f"\n{'='*50}")
    print(f"KẾT QUẢ: {passed}/{passed + failed} đạt")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "evidence_files_results.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"passed": passed, "failed": failed, "total": passed + failed,
                   "pass_rate_pct": round(passed / (passed + failed) * 100, 1), "details": results},
                  f, indent=2, ensure_ascii=False)
    print("Kết quả lưu tại tests/results/evidence_files_results.json")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)