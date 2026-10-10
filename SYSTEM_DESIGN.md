# Quy trình nghiệp vụ — IR Platform Đề tài 10

Oct 10, 2026 · @NgocHien

## Tổng quan hệ thống

Hệ thống quản lý vòng đời sự cố an ninh mạng (Incident Response Platform) dành cho tổ chức vừa và nhỏ, tích hợp AI phân loại cảnh báo và ánh xạ MITRE ATT&CK. Được thiết kế theo NIST SP 800-61 Rev.2 lifecycle với tham chiếu CSF 2.0.

**Mục tiêu:** Chuẩn hóa quy trình tiếp nhận cảnh báo → phân tích → xử lý → phục hồi → học hỏi mà không cần xây dựng SIEM thương mại đầy đủ.

**Phạm vi MVP:**

- Web quản lý tài sản, cảnh báo, incident, bằng chứng, task, phê duyệt, phục hồi và postmortem
- Nhập cảnh báo từ CSV/JSON/webhook mô phỏng
- Một mô hình phân loại cảnh báo mạng (CIC-IDS2017) và ánh xạ ATT&CK bằng retrieval
- Dashboard SLA và timeline; chưa tích hợp tự động với firewall/EDR thật

**Tech stack:**

| Tầng | Công nghệ |
| --- | --- |
| Frontend | React 18 + Vite + Tailwind CSS |
| Backend | Python FastAPI + SQLAlchemy |
| Database | Microsoft SQL Server |
| AI Service |Local FastAPI |
| ML | scikit-learn Random Forest, TF-IDF |
| Auth | JWT (access 15 phút, refresh 7 ngày) + bcrypt |

## Role và phân quyền

Hệ thống có 3 role, ánh xạ với cấu trúc SOC thực tế tại tổ chức vừa và nhỏ.

| Role | Tương đương thực tế | Trách nhiệm chính |
| --- | --- | --- |
| `it_helpdesk` | Tier 1 SOC / IT Staff | Tiếp nhận cảnh báo, thu thập bằng chứng, thực hiện containment theo chỉ đạo, eradication & recovery |
| `analyst_soc` | Tier 2 SOC / Incident Responder | Triage, tạo incident, phân tích IOC, phê duyệt containment, viết postmortem, gửi thông báo |
| `stakeholder` | Business Owner / Management | Xác nhận recovery, đọc thông báo, xem dashboard |

**Permission matrix chi tiết:**

| Hành động | IT/Helpdesk | Analyst/SOC | Stakeholder |
| --- | --- | --- | --- |
| Xem tất cả dữ liệu | ✅ | ✅ | ✅ |
| Tạo / upload alert | ✅ | ✅ | ❌ |
| Triage alert | ✅ | ✅ | ❌ |
| Tạo incident | ❌ | ✅ | ❌ |
| Thu thập bằng chứng | ✅ | ✅ | ❌ |
| Lock bằng chứng | ✅ | ✅ | ❌ |
| Phân tích phạm vi & IOC | ❌ | ✅ | ❌ |
| Đề xuất containment | ✅ | ✅ | ❌ |
| Phê duyệt containment | ❌ | ✅ | ❌ |
| Thực hiện containment | ✅ | ✅ | ❌ |
| Recovery action | ✅ | ✅ | ❌ |
| Xác nhận recovery | ❌ | ✅ | ✅ |
| Tạo & gửi thông báo | ❌ | ✅ | ❌ |
| Viết postmortem | ❌ | ✅ | ❌ |
| Xóa tài sản | ❌ | ✅ | ❌ |
| Gọi AI suggest | ✅ | ✅ | ✅ |

**Lý do thiết kế:** IT/Helpdesk được triage vì trong SME, Tier 1 thường triage sơ bộ trước khi escalate lên Analyst. Stakeholder không tạo/sửa dữ liệu kỹ thuật nhưng có quyền xác nhận recovery vì họ là người chịu trách nhiệm về hệ thống nghiệp vụ. Mọi thao tác có rủi ro (containment) đều yêu cầu phê duyệt từ Analyst trước khi thực hiện.

## Quy trình nghiệp vụ 12 bước

Mỗi bước mô tả ai làm gì, đầu vào, đầu ra và điều kiện chuyển tiếp.

### Bước 1 — Quản lý tài sản

**Ai làm:** IT/Helpdesk, Analyst/SOC **Đầu vào:** Thông tin máy chủ, ứng dụng, tài khoản **Đầu ra:** Danh mục tài sản với mức quan trọng (critical/high/medium/low) **Ghi chú:** Làm trước khi có sự cố. Tài sản được liên kết với cảnh báo và incident để đánh giá mức độ ảnh hưởng.

### Bước 2 — Tiếp nhận cảnh báo

**Ai làm:** IT/Helpdesk, Analyst/SOC **Đầu vào:** File CSV/JSON, POST webhook, hoặc nhập thủ công **Đầu ra:** Alert với status `new`, có ID, timestamp, nguồn gốc **Ghi chú:** Mọi cảnh báo đều vào hàng chờ, chưa phán xét. Webhook endpoint cho phép tích hợp IDS/IPS mô phỏng.

### Bước 3 — Chuẩn hóa & chống trùng

**AI làm:** Hệ thống tự động (gọi sau mỗi lần tạo alert) **Đầu vào:** Alert mới tạo **Đầu ra:** Alert được gán `group_id`, các alert cùng IOC trong 60 phút được gom nhóm **Ghi chú:** Chuẩn hóa IOC về lowercase, loại trùng. Giữ link về alert gốc. Tham số cửa sổ thời gian (60 phút) có thể cấu hình.

### Bước 4 — Triage

**Ai làm:** IT/Helpdesk (sơ bộ), Analyst/SOC (chính thức) **Đầu vào:** Alert ở trạng thái `new` hoặc `reviewing` **Đầu ra:** Alert với loại tấn công, mức độ, độ tin cậy, SLA deadline, người phụ trách **Điều kiện:** AI suggest có thể điền sẵn mức độ và ATT&CK technique — Analyst xác nhận trước khi lưu **Nhánh:** Đủ thông tin → `triaged` → Bước 5 | False positive → `false_positive` → đóng

### Bước 5 — Tạo incident

**Ai làm:** Analyst/SOC **Đầu vào:** Alert ở trạng thái `triaged` hoặc `escalated` **Đầu ra:** Incident với ID, commander, checklist ban đầu, liên kết đến các alert **Ghi chú:** Một incident có thể gộp nhiều alert liên quan. Tất cả alert được gán `incident_id` và chuyển sang `escalated`.

### Bước 6 — Thu thập bằng chứng

**Ai làm:** IT/Helpdesk, Analyst/SOC **Đầu vào:** Log, email, file, hash, screenshot **Đầu ra:** Evidence với SHA-256 hash tự tính, chain of custody log **Ghi chú:** Mỗi thao tác (thu thập, xem, lock) đều ghi vào chain of custody. Sau khi lock, bằng chứng không thể sửa.

### Bước 7 — Phân tích & phạm vi ảnh hưởng

**Ai làm:** Analyst/SOC **Đầu vào:** Bằng chứng đã thu thập, IOC, tài sản **Đầu ra:** Danh sách IOC, tài sản/tài khoản bị ảnh hưởng, ATT&CK techniques, tóm tắt phân tích **Ghi chú:** AI đề xuất Top-K ATT&CK techniques qua retrieval + reranking. Lưu phiên bản ATT&CK tại thời điểm ánh xạ.

### Bước 8 — Containment

**Ai làm:** IT/Helpdesk (đề xuất + thực hiện), Analyst/SOC (phê duyệt) **Đầu vào:** Kết quả phân tích phạm vi **Đầu ra:** Log hành động containment có timestamp, người thực hiện, ghi chú `[MÔ PHỎNG]` **Flow:** IT đề xuất (`proposed`) → Analyst phê duyệt (`approved`/`rejected`) → IT thực hiện (`executed`) **Quan trọng:** MVP chỉ mô phỏng — không tự động khóa tài khoản hay cô lập máy trên hệ thống thật.

### Bước 9 — Eradication & Recovery

**Ai làm:** IT/Helpdesk (thực hiện), Stakeholder + Analyst (xác nhận) **Đầu vào:** Incident đã `contained` **Đầu ra:** Danh sách recovery actions với trạng thái, confirmation từ Stakeholder **Điều kiện đóng:** Tất cả recovery actions phải được confirm trước khi incident chuyển sang `recovering`.

### Bước 10 — Thông báo & phối hợp

**Ai làm:** Analyst/SOC (tạo + gửi), bất kỳ ai (acknowledge) **Đầu vào:** Nội dung cập nhật sự cố **Đầu ra:** Log thông báo với subject, recipients, thời gian gửi, người xác nhận đã đọc **Flow:** Draft → Analyst phê duyệt nội dung → Gửi → Stakeholder acknowledge

### Bước 11 — Đóng vụ & Postmortem

**Ai làm:** Analyst/SOC **Đầu vào:** Incident đã `recovering`, mọi recovery action đã confirmed **Đầu ra:** Postmortem với root cause, timeline, impact, lessons learned, action items có owner và deadline **Điều kiện đóng:** Finalize postmortem → incident tự động chuyển sang `closed`, `resolved_at` được ghi.

### Bước 12 — Đo lường

**Ai làm:** Hệ thống tự động tính, tất cả role xem được **Đầu ra:** MTTD, MTTA, MTTR, số vụ mở, lỗi lặp, % hoàn thành action items, SLA breached alerts **Ghi chú:** Dashboard cập nhật real-time mỗi lần gọi API. MTTD/MTTA tính từ timestamp của alert và triage.

## Luồng dữ liệu & State machine

### Luồng tổng thể

&#91;embedded content: luồng nghiệp vụ · 12 bước · 3 row\]

```
Nguồn ngoài (IDS/email/manual)
    ↓ upload CSV / POST webhook
Alert (status: new)
    ↓ chuẩn hóa + dedup tự động
AlertGroup (gom theo IOC)
    ↓ triage (IT hoặc Analyst)
Alert (status: triaged)
    ↓ tạo incident (Analyst)
Incident (status: open)
    ↓ thu thập bằng chứng + phân tích
Evidence + ImpactAnalysis
    ↓ đề xuất containment (IT) → phê duyệt (Analyst)
Containment (status: executed) → Incident (status: contained)
    ↓ eradication & recovery (IT) → xác nhận (Stakeholder)
RecoveryAction (is_confirmed: true) → Incident (status: recovering)
    ↓ thông báo (Analyst)
Communication (status: acknowledged)
    ↓ postmortem (Analyst) → finalize
Postmortem (is_finalized: true) → Incident (status: closed)
    ↓ tự động tính metrics
Dashboard (MTTD, MTTA, MTTR, SLA...)
```

### State machine — Alert

| Trạng thái | Chuyển sang | Điều kiện |
| --- | --- | --- |
| `new` | `reviewing` | Analyst mở xem |
| `new` / `reviewing` | `triaged` | Triage thành công |
| `new` / `reviewing` | `false_positive` | Analyst đánh dấu FP |
| `triaged` | `escalated` | Tạo incident gộp alert này |
| `escalated` | — | Trạng thái cuối (theo dõi qua incident) |

### State machine — Incident

| Trạng thái | Chuyển sang | Điều kiện |
| --- | --- | --- |
| `open` | `investigating` | Analyst cập nhật thủ công |
| `investigating` | `contained` | IT thực hiện containment được phê duyệt |
| `contained` | `recovering` | Tất cả recovery actions được Stakeholder/Analyst confirm |
| `recovering` | `closed` | Analyst finalize postmortem |

### State machine — Containment

| Trạng thái | Chuyển sang | Điều kiện |
| --- | --- | --- |
| `proposed` | `approved` | Analyst phê duyệt |
| `proposed` | `rejected` | Analyst từ chối |
| `approved` | `executed` | IT thực hiện (chỉ mô phỏng) |

### State machine — Evidence

| Trạng thái | Chuyển sang | Điều kiện |
| --- | --- | --- |
| `is_locked: false` | `is_locked: true` | IT hoặc Analyst lock |
| `is_locked: true` | — | Không thể sửa sau khi lock |

## Module AI/ML

AI service chạy độc lập tại `http://localhost:8001`, backend gọi qua HTTP khi cần.

### Mô hình phân loại cảnh báo mạng

**Dataset:** CIC-IDS2017 (Canadian Institute for Cybersecurity) — 2.8M network flow records, 78 features, 15 loại tấn công + BENIGN.

**Mô hình:** Random Forest (100 trees, max\_depth=20, class\_weight=balanced)

**Kết quả:**

| Chỉ số | Giá trị |
| --- | --- |
| PR-AUC | 0.9998 |
| ROC-AUC | 0.9999 |
| Accuracy | \~99.9% |
| False Negative | 82 / 111,311 attack samples |

**Ngưỡng 3 vùng:**

| Vùng | Ngưỡng | Hành động |
| --- | --- | --- |
| auto\_close | prob < 0.15 | Tự đóng (BENIGN chắc chắn) |
| review | 0.15 ≤ prob < 0.80 | Analyst xem xét |
| urgent | prob ≥ 0.80 | Ưu tiên khẩn |

### ATT&CK Retrieval + Reranking

**Dữ liệu:** MITRE ATT&CK Enterprise v14.1 — 697 techniques (không revoked, không deprecated)

**Quy trình:**

1. Vectorize description + detection hints của 697 techniques bằng TF-IDF (10,000 features, bigram)
2. Nhận query từ alert (title + description + IOC)
3. Retrieval: cosine similarity → Top-20 candidates
4. Reranking: boost score nếu tên technique xuất hiện trong query, boost thêm nếu tactic keywords khớp
5. Trả về Top-K results với score

**Lưu phiên bản:** `models/attck_version.json` ghi version và timestamp lúc index.

### Tích hợp vào hệ thống

Endpoint `/ai/alert/suggest` trong backend nhận title + description + IOC, gọi AI service, trả về:

- `severity_suggestion`: mức độ đề xuất (critical/high/medium/low)
- `attck_techniques`: Top-5 techniques với id, tên, tactic, score
- `summary`: tóm tắt ngắn gọn bằng tiếng Việt
- `ai_generated: true` — đánh dấu rõ nội dung do AI tạo
- `warning`: nhắc Analyst xác nhận trước khi sử dụng

**Bảo mật:** Sanitize input trước khi xử lý (chống prompt injection), giới hạn độ dài 2000 ký tự, từ chối các pattern nguy hiểm.

### Kết quả benchmark

| Tiêu chí | Không có AI | Có AI | Cải thiện |
| --- | --- | --- | --- |
| Tỷ lệ phân loại đúng severity | 28.6% | 85.7% | +57.1% |
| Thời gian API call triage | 2.05s | 4.50s | +2.45s overhead |

## API Endpoints chính

Base URL: `http://localhost:8000` | Docs: `http://localhost:8000/docs`

### Auth

| Method | Endpoint | Mô tả | Role |
| --- | --- | --- | --- |
| POST | `/auth/register` | Tạo tài khoản | Public |
| POST | `/auth/login` | Đăng nhập, nhận JWT | Public |

### Assets

| Method | Endpoint | Mô tả | Role |
| --- | --- | --- | --- |
| GET | `/assets/` | Danh sách tài sản | All |
| POST | `/assets/` | Tạo tài sản | IT, Analyst |
| PUT | `/assets/{id}` | Cập nhật | IT, Analyst |
| DELETE | `/assets/{id}` | Xóa | Analyst |

### Alerts

| Method | Endpoint | Mô tả | Role |
| --- | --- | --- | --- |
| GET | `/alerts/` | Danh sách (filter theo status) | All |
| POST | `/alerts/` | Tạo thủ công | IT, Analyst |
| POST | `/alerts/webhook` | Nhận từ hệ thống ngoài | IT, Analyst |
| POST | `/alerts/upload/csv` | Upload CSV | IT, Analyst |
| POST | `/alerts/upload/json` | Upload JSON | IT, Analyst |
| PATCH | `/alerts/{id}/triage` | Triage alert | IT, Analyst |
| PATCH | `/alerts/{id}/false-positive` | Đánh dấu FP | Analyst |
| GET | `/alerts/groups/list` | Xem nhóm dedup | All |

### Incidents

| Method | Endpoint | Mô tả | Role |
| --- | --- | --- | --- |
| GET | `/incidents/` | Danh sách | All |
| POST | `/incidents/` | Tạo từ alert | Analyst |
| GET | `/incidents/{id}` | Chi tiết | All |
| PATCH | `/incidents/{id}/status` | Cập nhật trạng thái | Analyst |
| GET | `/incidents/{id}/alerts` | Alerts thuộc incident | All |

### Evidences

| Method | Endpoint | Mô tả | Role |
| --- | --- | --- | --- |
| POST | `/incidents/{id}/evidences/` | Thu thập bằng chứng | IT, Analyst |
| PATCH | `/incidents/{id}/evidences/{eid}/lock` | Lock bằng chứng | IT, Analyst |
| GET | `/incidents/{id}/evidences/{eid}/custody` | Chain of custody | All |

### Containment / Recovery / Communication / Postmortem

| Method | Endpoint | Mô tả | Role |
| --- | --- | --- | --- |
| POST | `/incidents/{id}/containments/` | Đề xuất containment | IT, Analyst |
| PATCH | `/incidents/{id}/containments/{cid}/review` | Phê duyệt | Analyst |
| PATCH | `/incidents/{id}/containments/{cid}/execute` | Thực hiện | IT, Analyst |
| POST | `/incidents/{id}/recovery/` | Tạo recovery action | IT, Analyst |
| PATCH | `/incidents/{id}/recovery/{rid}/confirm` | Xác nhận recovery | Analyst, Stakeholder |
| POST | `/incidents/{id}/communications/` | Tạo thông báo | Analyst |
| PATCH | `/incidents/{id}/communications/{cid}/send` | Gửi | Analyst |
| POST | `/incidents/{id}/postmortem/` | Viết postmortem | Analyst |
| PATCH | `/incidents/{id}/postmortem/finalize` | Finalize + đóng incident | Analyst |

### Dashboard & AI

| Method | Endpoint | Mô tả | Role |
| --- | --- | --- | --- |
| GET | `/dashboard/` | 6 chỉ số + stats | All |
| GET | `/dashboard/sla` | Alerts vi phạm SLA | All |
| POST | `/ai/alert/suggest` | AI đề xuất severity + ATT&CK | All |
| POST | `/ai/attck/search` | Tìm kiếm ATT&CK techniques | All |
| GET | `/ai/health` | Kiểm tra AI service | All |
