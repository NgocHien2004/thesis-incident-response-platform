"""Kiểm thử đọc .eml và .zip trong backend/app/services/parsing.py (không cần chạy backend hay dịch vụ AI).
Chạy: python tests/test_eml_parsing.py"""
import csv
import io
import json
import os
import sys
import tempfile
import zipfile
from email.message import EmailMessage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
from app.services import parsing                                      # noqa: E402
from app.services.parsing import Schema, ValidationError, iter_rows, validate_file   # noqa: E402

passed = failed = 0


def check(label, cond, note=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✓ PASS | {label}")
    else:
        failed += 1
        print(f"  ✗ FAIL | {label}" + (f" — {note}" if note else ""))


def raises(fn, text=None):
    try:
        fn()
    except ValidationError as e:
        return text is None or text in str(e)
    return False


def plain(subject="Họp tuần", body="Lịch họp thứ hai, xem http://corp.vn/lich.", sender="Sếp <boss@corp.vn>"):
    m = EmailMessage()
    m["Subject"], m["From"], m["To"] = subject, sender, "me@corp.vn"
    m.set_content(body)
    return m


def tmp(data, suffix):
    f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    f.write(data if isinstance(data, bytes) else data.encode("utf-8"))
    f.close()
    return f.name


def make_zip(files):
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".zip").name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return path


EMAIL = Schema("email")

print("── 1. Một thư .eml thuần văn bản ──")
r = parsing.parse_eml(plain().as_bytes())
check("Tiêu đề tiếng Việt được giải mã", r["subject"] == "Họp tuần", r["subject"])
check("Người gửi lấy đúng địa chỉ", r["sender"] == "boss@corp.vn", r["sender"])
check("URL cuối câu không dính dấu chấm", r["urls"] == ["http://corp.vn/lich"], str(r["urls"]))
check("Không có HTML, không có đính kèm", r["has_html"] is False and r["attachments"] == [])
p = tmp(plain().as_bytes(), ".eml")
check("validate_file nhận 1 dòng", validate_file(p, "eml", EMAIL, 100) == 1)
row = list(iter_rows(p, "eml", EMAIL))[0]
check("Dòng chuẩn hóa đủ cột email", row[0] == 1 and {"subject", "body", "sender", "urls"} <= set(row[1]))

print("\n── 2. Thư HTML ──")
m = EmailMessage()
m["Subject"], m["From"] = "Xác minh tài khoản", "Ngan hang <support@bank-secure.example>"
m.set_content("Xem bản HTML")
m.add_alternative('<html><body><p>Vui lòng <a href="http://evil.example/login">http://bank.vn/dang-nhap</a> ngay.</p>'
                  '<script>var x="http://tracker.example"</script></body></html>', subtype="html")
r = parsing.parse_eml(m.as_bytes())
check("Phần thuần quá ngắn thì dùng chữ từ HTML", "Vui lòng" in r["body"] and "<p>" not in r["body"], r["body"])
check("Có cờ has_html", r["has_html"] is True)
check("Lấy cả liên kết ẩn trong href lẫn chữ hiển thị", "http://evil.example/login" in r["urls"] and "http://bank.vn/dang-nhap" in r["urls"], str(r["urls"]))
check("Bỏ nội dung script", "tracker" not in r["body"] and "http://tracker.example" not in r["urls"])
m2 = EmailMessage()
m2["Subject"] = "Thư đủ dài"
m2.set_content("Đây là phần văn bản thuần khá dài, đủ để dùng làm nội dung chính của thư này.")
m2.add_alternative("<html><body><p>Bản HTML trùng nội dung</p></body></html>", subtype="html")
r = parsing.parse_eml(m2.as_bytes())
check("Có cả hai phần thì ưu tiên văn bản thuần, không nhân đôi nội dung", "Bản HTML" not in r["body"] and "văn bản thuần" in r["body"])

print("\n── 3. Tệp đính kèm chỉ ghi tên ──")
m = plain("Hóa đơn", "Xem file đính kèm")
m.add_attachment(b"%PDF-1.4 NOI_DUNG_BI_MAT", maintype="application", subtype="pdf", filename="hoa_don.pdf")
r = parsing.parse_eml(m.as_bytes())
check("Ghi tên tệp đính kèm", r["attachments"] == ["hoa_don.pdf"], str(r["attachments"]))
check("Không đưa nội dung tệp vào thư", "NOI_DUNG_BI_MAT" not in r["body"] and "PDF" not in r["body"])

print("\n── 4. Mã hóa lạ, thư hỏng ──")
raw = (b"From: a@b.com\r\nSubject: =?iso-8859-1?q?Caf=E9?=\r\nContent-Type: text/plain; charset=iso-8859-1\r\n"
       b"Content-Transfer-Encoding: 8bit\r\n\r\nCaf\xe9 au lait\r\n")
r = parsing.parse_eml(raw)
check("Đọc được charset latin-1", "Café" in r["subject"] and "Café" in r["body"], f"{r['subject']!r} {r['body']!r}")
raw = b"From: a@b.com\r\nSubject: x\r\nContent-Type: text/plain; charset=khong-co-that\r\n\r\nNoi dung van doc duoc\r\n"
check("Charset không tồn tại không làm hỏng", "Noi dung" in parsing.parse_eml(raw)["body"])
check("Thư rỗng bị từ chối, báo rõ", raises(lambda: parsing.parse_eml(b"", "rong.eml"), "rong.eml"))
check("Chuỗi bất kỳ không phải thư thì không có nội dung và bị từ chối", raises(lambda: parsing.parse_eml(b"\x00\x01\x02")))

print("\n── 5. File ZIP ──")
zp = make_zip({"b_thu2.eml": plain("Thư hai", "Nội dung hai").as_bytes(), "a_thu1.eml": plain("Thư một", "Nội dung một").as_bytes(),
               "thu_muc/c_thu3.EML": plain("Thư ba", "Nội dung ba").as_bytes(), "ghi_chu.txt": b"khong phai thu",
               "__MACOSX/a_thu1.eml": b"rac", "thu_muc/._c_thu3.eml": b"rac"})
check("Đếm đúng 3 thư, bỏ file .txt và rác macOS", validate_file(zp, "zip", EMAIL, 100) == 3)
rows = list(iter_rows(zp, "zip", EMAIL))
check("Thứ tự theo tên file", [r[1]["subject"] for r in rows] == ["Thư một", "Thư hai", "Thư ba"], str([r[1]["subject"] for r in rows]))
check("Lưu tên file gốc trong dòng", rows[0][1]["source_file"] == "a_thu1.eml" and rows[2][1]["source_file"] == "thu_muc/c_thu3.EML")
check("Chạy hai lần cho cùng kết quả (validate rồi xử lý)", [r[1]["subject"] for r in list(iter_rows(zp, "zip", EMAIL))] == [r[1]["subject"] for r in rows])
check("Vượt max_rows bị từ chối", raises(lambda: validate_file(zp, "zip", EMAIL, 2), "vượt quá"))
check("ZIP không có .eml bị từ chối", raises(lambda: validate_file(make_zip({"a.txt": b"x"}), "zip", EMAIL, 100), "không chứa"))
check("File không phải ZIP bị từ chối", raises(lambda: validate_file(tmp(b"khong phai zip", ".zip"), "zip", EMAIL, 100), "ZIP"))
check("Một thư rỗng trong ZIP làm hỏng cả file và nêu tên thư", raises(
    lambda: validate_file(make_zip({"tot.eml": plain().as_bytes(), "hong.eml": b""}), "zip", EMAIL, 100), "hong.eml"))

print("\n── 6. Giới hạn dung lượng ──")
old_eml, old_total = parsing.MAX_EML_BYTES, parsing.MAX_ZIP_TOTAL_BYTES
parsing.MAX_EML_BYTES = 200
check(".eml quá lớn bị từ chối", raises(lambda: validate_file(tmp(plain(body="x" * 500).as_bytes(), ".eml"), "eml", EMAIL, 10), "lớn hơn"))
check("Thư quá lớn trong ZIP bị từ chối", raises(lambda: validate_file(make_zip({"to.eml": plain(body="x" * 500).as_bytes()}), "zip", EMAIL, 10), "to.eml"))
parsing.MAX_EML_BYTES = old_eml
parsing.MAX_ZIP_TOTAL_BYTES = 300
check("Tổng dung lượng giải nén vượt mức bị từ chối", raises(lambda: validate_file(
    make_zip({"a.eml": plain(body="y" * 200).as_bytes(), "b.eml": plain(body="y" * 200).as_bytes()}), "zip", EMAIL, 10), "giải nén"))
parsing.MAX_ZIP_TOTAL_BYTES = old_total

print("\n── 7. CSV và JSON email vẫn hoạt động ──")
buf = io.StringIO()
w = csv.writer(buf)
w.writerow(["subject", "body", "sender", "urls"])
w.writerow(["Free money", "Claim now", "x@y.com", "http://a.com http://b.com"])
cp = tmp(buf.getvalue(), ".csv")
check("CSV email nhận 1 dòng", validate_file(cp, "csv", EMAIL, 10) == 1)
row = list(iter_rows(cp, "csv", EMAIL))[0][1]
check("CSV: urls tách đúng, has_html mặc định False", row["urls"] == ["http://a.com", "http://b.com"] and row["has_html"] is False and row["attachments"] == [])
jp = tmp(json.dumps([{"subject": "A", "body": "B", "sender": "s@x.com", "urls": ["http://p.com"], "has_html": True,
                      "attachments": "a.pdf;b.zip"}]), ".json")
row = list(iter_rows(jp, "json", EMAIL))[0][1]
check("JSON: has_html và attachments được nhận", row["has_html"] is True and row["attachments"] == ["a.pdf", "b.zip"], str(row))

print("\n── 8. Nguồn luồng mạng không nhận thư ──")
check(".eml với mô hình luồng mạng bị từ chối vì thiếu cột", raises(lambda: validate_file(p, "eml", Schema("network", [" Flow Duration"]), 10), "Thiếu"))

print(f"\n{'=' * 50}\nKẾT QUẢ: {passed} PASS / {failed} FAIL / {passed + failed} tổng\n{'=' * 50}")
sys.exit(0 if failed == 0 else 1)