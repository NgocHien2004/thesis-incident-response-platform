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

Đề bài liệt kê 7 **nhóm người dùng**. Đây là các nhóm người trong tổ chức, không phải 7 vai trò kỹ thuật, nên hệ thống gộp chúng thành 3 vai trò theo quyền hạn thực tế.

| # | Nhóm trong đề | Vai trò hệ thống | Cách xử lý |
| --- | --- | --- | --- |
| 1 | Nhân viên gửi báo cáo phishing | không cần tài khoản | Báo qua email hoặc điện thoại cho helpdesk, helpdesk nhập vào hệ thống (bước 2: "email nghi phishing, báo cáo thủ công") |
| 2 | IT/helpdesk | `it_helpdesk` | |
| 3 | Chuyên viên an ninh/SOC | `analyst_soc` | |
| 4 | Incident commander / quản lý CNTT | `analyst_soc` được chỉ định làm commander của từng vụ (`commander_id`) | Commander là vai trò theo từng incident, có thẩm quyền cao hơn trong phạm vi vụ đó |
| 5 | Chủ hệ thống / nghiệp vụ bị ảnh hưởng | `stakeholder` | |
| 6 | Lãnh đạo, pháp chế, truyền thông | `stakeholder` | Đề ghi "trong kịch bản mô phỏng", nên là vai diễn, không cần role riêng |
| 7 | Kiểm toán viên | `analyst_soc` | Hệ thống không có vai trò kiểm toán riêng. Việc xem, xuất và kiểm tra toàn vẹn nhật ký kiểm toán do Analyst đảm nhiệm; mọi thao tác của chính Analyst vẫn nằm trong nhật ký |

| Role | Tương đương thực tế | Trách nhiệm chính |
| --- | --- | --- |
| `it_helpdesk` | Tier 1 SOC / IT Staff | Tiếp nhận và triage sơ bộ cảnh báo, thu thập bằng chứng, đề xuất và thực hiện containment, thực hiện recovery |
| `analyst_soc` | Tier 2 SOC / Incident Responder | Triage, tạo incident (người tạo mặc định là commander), phân tích phạm vi, phê duyệt containment, xác minh, soạn và duyệt thông báo, postmortem, xem và xuất nhật ký kiểm toán, cấp tài khoản |
| `stakeholder` | Chủ hệ thống / Lãnh đạo | Xác nhận recovery, xác nhận đã nhận thông báo, xem dữ liệu |

**Ma trận quyền:**

| Hành động | IT | Analyst | Stakeholder |
| --- | --- | --- | --- |
| Xem dữ liệu (alert, incident, tài sản, dashboard, timeline) | ✅ | ✅ | ✅ |
| Tạo, sửa tài sản | ✅ | ✅ | ❌ |
| Xóa tài sản | ❌ | ✅ | ❌ |
| Tạo / upload alert; triage | ✅ | ✅ | ❌ |
| Đánh dấu báo nhầm; tạo incident; đổi trạng thái incident; phân tích phạm vi | ❌ | ✅ | ❌ |
| Thu thập và khóa bằng chứng | ✅ | ✅ | ❌ |
| Đề xuất containment | ✅ | ✅ | ❌ |
| Phê duyệt containment | ❌ | ✅ (xem quy tắc bên dưới) | ❌ |
| Thực hiện containment | ✅ | ✅ | ❌ |
| Xác minh containment | ❌ | ✅ (người khác người thực hiện) | ❌ |
| Tạo, cập nhật hành động recovery | ✅ | ✅ | ❌ |
| Xác nhận recovery | ❌ | ❌ | ✅ |
| Soạn thông báo | ❌ | ✅ | ❌ |
| Phê duyệt thông báo | ❌ | ✅ (người khác người soạn) | ❌ |
| Gửi thông báo đã duyệt | ❌ | ✅ | ❌ |
| Xác nhận đã nhận thông báo | ❌ | ❌ | ✅ |
| Viết postmortem | ❌ | ✅ | ❌ |
| Đánh dấu hoàn thành action item | ✅ | ✅ | ❌ |
| Xem playbook và công việc của incident | ✅ | ✅ | ✅ |
| Tạo, sửa, ngừng dùng playbook | ❌ | ✅ | ❌ |
| Áp dụng playbook; giao việc, đặt hạn; tạo hoặc xóa công việc thủ công | ❌ | ✅ | ❌ |
| Nhận việc, làm và hoàn thành công việc (việc giao cho mình, hoặc việc chưa giao thuộc IT) | ✅ | ✅ | ❌ |
| Bỏ qua hoặc mở lại công việc | ❌ | ✅ (việc bắt buộc chỉ commander; luôn ghi lý do) | ❌ |
| Đóng hoặc mở lại incident; chốt postmortem | ❌ | ✅ (chỉ commander của vụ) | ❌ |
| Xem, xuất nhật ký kiểm toán; kiểm tra chuỗi băm | ❌ | ✅ | ❌ |
| Cấp tài khoản mới | ❌ | ✅ | ❌ |
| Gọi AI suggest | ✅ | ✅ | ✅ |

**Ma trận thẩm quyền và tách nhiệm vụ.** Đề yêu cầu quyền thực thi containment nằm trong ma trận thẩm quyền của tổ chức. Hệ thống áp dụng các quy tắc sau, kiểm tra ở backend và có trong bộ kiểm thử phân quyền:

- Người phê duyệt containment phải khác người đề xuất.
- Containment rủi ro cao chỉ do commander của vụ phê duyệt.
- Người xác minh containment phải khác người thực hiện.
- Người duyệt thông báo phải khác người soạn; thông báo ra ngoài hoặc leo thang do commander duyệt.
- Recovery chỉ do chủ hệ thống (stakeholder) xác nhận, analyst không xác nhận thay.
- Chỉ commander của vụ được đóng, mở lại incident và chốt postmortem.

**Bảo mật tài khoản.** Mật khẩu băm bcrypt. Token JWT hết hạn sau 15 phút. Sai mật khẩu 5 lần thì khóa tài khoản 15 phút. Tài khoản đầu tiên được tạo tự do để khởi tạo hệ thống; sau đó chỉ Analyst mới cấp tài khoản và phân vai trò. Mọi lần đăng nhập, đăng nhập sai và cấp tài khoản đều được ghi vào nhật ký kiểm toán.

**Lý do thiết kế.** Gộp thành 3 vai trò để phù hợp tổ chức vừa và nhỏ nhưng vẫn giữ được tách nhiệm vụ. Commander là vai trò theo từng vụ chứ không phải một loại tài khoản, đúng với NIST SP 800-61 và CISA playbook. Hệ thống không có vai trò kiểm toán viên riêng: chức năng nhật ký kiểm toán do Analyst dùng để tự rà soát và truy vết. Hạn chế: không có người kiểm tra độc lập với người vận hành, nên chuỗi băm là lớp bảo vệ chính cho tính toàn vẹn của nhật ký. Trong tổ chức thật, nên cấp thêm một vai trò chỉ đọc cho kiểm toán nội bộ.

## Quy trình nghiệp vụ 12 bước

Mỗi bước mô tả ai làm gì, đầu vào, đầu ra và điều kiện chuyển tiếp.

### Bước 1 — Quản lý tài sản

**Ai làm:** IT/Helpdesk, Analyst/SOC **Đầu vào:** Thông tin máy chủ, ứng dụng, tài khoản **Đầu ra:** Danh mục tài sản với mức quan trọng (critical/high/medium/low) **Ghi chú:** Làm trước khi có sự cố. Tài sản được liên kết với cảnh báo và incident để đánh giá mức độ ảnh hưởng.

### Bước 2 — Tiếp nhận cảnh báo

**Ai làm:** IT/Helpdesk, Analyst/SOC **Đầu vào:** File CSV/JSON, POST webhook, hoặc nhập thủ công **Đầu ra:** Alert với status `new`, có ID, timestamp, nguồn gốc **Ghi chú:** Mọi cảnh báo đều vào hàng chờ, chưa phán xét. Nhân viên báo cáo nghi phishing qua email hoặc điện thoại, helpdesk nhập vào hệ thống (nhân viên thường không có tài khoản). Chưa hỗ trợ nhập trực tiếp tệp email (.eml).

### Bước 3 — Chuẩn hóa & chống trùng

**AI làm:** Hệ thống tự động (gọi sau mỗi lần tạo alert) **Đầu vào:** Alert mới tạo **Đầu ra:** Alert được gán `group_id`, các alert cùng IOC trong 60 phút được gom nhóm **Ghi chú:** Chuẩn hóa IOC về lowercase, loại trùng. Giữ link về alert gốc. Tham số cửa sổ thời gian (60 phút) có thể cấu hình.

### Bước 4 — Triage

**Ai làm:** IT/Helpdesk (sơ bộ), Analyst/SOC (chính thức) **Đầu vào:** Alert ở trạng thái `new` hoặc `reviewing` **Đầu ra:** Alert với loại tấn công, mức độ, độ tin cậy, SLA deadline, người phụ trách **Điều kiện:** AI suggest có thể điền sẵn mức độ và ATT&CK technique — Analyst xác nhận trước khi lưu **Nhánh:** Đủ thông tin → `triaged` → Bước 5 | False positive → `false_positive` → đóng

### Bước 5 — Tạo incident

**Ai làm:** Analyst/SOC **Đầu vào:** Alert đã `triaged` **Đầu ra:** Incident với ID, commander, checklist ban đầu, liên kết đến các alert **Ghi chú:** Một incident có thể gộp nhiều alert liên quan; các alert chuyển sang `escalated`. Commander mặc định là người tạo, hoặc một Analyst khác được chỉ định; commander phải là tài khoản Analyst đang hoạt động. Khi tạo vụ có thể chọn một playbook; mỗi bước của playbook trở thành một công việc (task) của vụ, xem mục *Playbook và công việc*.

### Bước 6 — Thu thập bằng chứng

**Ai làm:** IT/Helpdesk, Analyst/SOC **Đầu vào:** Log, email, file, hash, screenshot **Đầu ra:** Evidence với SHA-256 hash tự tính, chain of custody log **Ghi chú:** Mỗi thao tác (thu thập, xem, lock) đều ghi vào chain of custody. Sau khi lock, bằng chứng không thể sửa.

### Bước 7 — Phân tích & phạm vi ảnh hưởng

**Ai làm:** Analyst/SOC **Đầu vào:** Bằng chứng đã thu thập, IOC, tài sản **Đầu ra:** Danh sách IOC, tài sản/tài khoản bị ảnh hưởng, ATT&CK techniques, tóm tắt phân tích **Ghi chú:** AI đề xuất Top-K ATT&CK techniques qua retrieval + reranking. Lưu phiên bản ATT&CK tại thời điểm ánh xạ.

### Bước 8 — Containment

**Ai làm:** IT/Helpdesk hoặc Analyst (đề xuất, thực hiện), Analyst khác (phê duyệt, xác minh) **Đầu vào:** Incident đang điều tra, đã khống chế hoặc đang phục hồi **Flow:** Đề xuất (`proposed`) → phê duyệt hoặc từ chối → thực hiện (`executed`) → xác minh (`verified`) **Quy tắc thẩm quyền:** người duyệt khác người đề xuất; rủi ro cao chỉ commander duyệt; người xác minh khác người thực hiện. **Quan trọng:** MVP chỉ mô phỏng, không tự động khóa tài khoản hay cô lập máy trên hệ thống thật; "thực hiện" chỉ ghi nhận việc con người đã làm kèm ghi chú.

### Bước 9 — Eradication & Recovery

**Ai làm:** IT/Helpdesk hoặc Analyst (thực hiện), Stakeholder là chủ hệ thống (xác nhận) **Đầu vào:** Incident đã `contained` **Đầu ra:** Danh sách recovery actions với trạng thái và xác nhận của chủ hệ thống **Ghi chú:** Khi mọi hành động đã xong được chủ hệ thống xác nhận, incident chuyển sang `recovering`. Analyst không được xác nhận thay chủ hệ thống.

### Bước 10 — Thông báo & phối hợp

**Ai làm:** Analyst/SOC (soạn, duyệt, gửi), Stakeholder (xác nhận đã nhận) **Đầu ra:** Log thông báo với subject, recipients, thời gian gửi, người xác nhận đã đọc **Flow:** Nháp → Analyst khác người soạn phê duyệt nội dung → gửi → Stakeholder xác nhận. Thông báo ra ngoài hoặc leo thang cần commander phê duyệt. Chưa có mẫu thông báo và danh bạ bên liên quan.

### Bước 11 — Đóng vụ & Postmortem

**Ai làm:** Commander của vụ (đóng, chốt postmortem), Analyst (viết postmortem) **Tiêu chí đóng:** đã có mốc khống chế; không còn đề xuất containment chưa xử lý; mọi containment đã thực hiện đều được xác minh; không còn hành động recovery đang chờ hoặc đang làm; có ít nhất một hành động recovery được chủ hệ thống xác nhận; không còn công việc bắt buộc theo playbook ở trạng thái chưa làm hoặc đang làm (công việc bắt buộc phải xong, hoặc được commander bỏ qua kèm lý do). **Postmortem:** viết khi incident đã sang giai đoạn phục hồi hoặc đã đóng; chốt (finalize) khi incident đã đóng và có ít nhất một action item; chốt không thay đổi trạng thái hay thời điểm đóng của incident. **Mở lại:** commander có thể mở lại incident đã đóng kèm lý do bắt buộc. Incident đã đóng không nhận thêm bằng chứng, containment hay recovery.

### Bước 12 — Đo lường

**Ai làm:** Hệ thống tự động tính, tất cả role xem được **Đầu ra:** MTTD, MTTA, MTTR, số vụ mở, lỗi lặp, % hoàn thành action items, SLA breached alerts **Định nghĩa:** MTTD là thời gian từ cảnh báo đầu tiên của vụ đến khi mở incident; MTTA là thời gian từ lúc tạo cảnh báo đến khi được triage; MTTR là thời gian từ khi mở incident đến khi đóng. MTTD và MTTR tính trên các vụ đã đóng. Vi phạm SLA là cảnh báo đã triage, quá hạn mà chưa được nâng thành incident. **Hạn chế:** chỉ số "lỗi lặp" so khớp chuỗi nguyên nhân gốc nên chưa đáng tin.

### Playbook và công việc (task)

Đề yêu cầu chuyển các phase, checklist, điểm phê duyệt và tiêu chí đóng của playbook CISA thành mẫu cấu hình được cho doanh nghiệp vừa và nhỏ. Hệ thống cài đặt hai đối tượng:

- **Playbook** là mẫu theo loại sự cố (`phishing`, `credential_compromise`, `malware`, `web_attack`, `other`), gồm các bước có thứ tự. Mỗi bước có tiêu đề, mô tả, giai đoạn (`analysis`, `evidence`, `containment`, `recovery`, `communication`, `closure`), vai trò thường đảm nhiệm (IT/Helpdesk hoặc Analyst/SOC), hạn tính bằng giờ kể từ lúc tạo vụ, và cờ bắt buộc. Hệ thống nạp sẵn 5 playbook mẫu: 4 playbook theo loại sự cố do tác giả soạn dựa trên CISA Incident and Vulnerability Response Playbooks và NIST SP 800-61 Rev. 3, và 1 playbook tham chiếu chuẩn bám cấu trúc checklist của CISA (xem mục sau). Analyst tạo, sửa hoặc ngừng dùng playbook trên giao diện. Nội dung mẫu là điều chỉnh của tác giả, không phải bản sao tài liệu gốc.
- **Công việc (task)** là bản sao của một bước playbook gắn với một incident, hoặc do Analyst tạo tay. Task lưu tiêu đề, giai đoạn, hạn, cờ bắt buộc, người được giao, ghi chú và người hoàn thành. Vì là bản sao, sửa hoặc ngừng dùng playbook về sau không làm đổi các task đã tạo.

### Playbook tham chiếu chuẩn và đối chiếu với CISA

CISA không có playbook riêng theo loại sự cố: tài liệu chỉ có một playbook ứng phó sự cố chung và một playbook xử lý lỗ hổng, và playbook ứng phó chỉ áp dụng cho hoạt động độc hại đã xác nhận có thể thành sự cố lớn. Tài liệu còn nêu rõ không áp dụng cho các hoạt động không có khả năng thành sự cố lớn, ví dụ người dùng nhấp email phishing mà không bị chiếm quyền, hay mã độc thông thường trên một máy. Nhiều bước chỉ dành cho cơ quan liên bang Mỹ (báo CISA trong 1 giờ, báo OMB và Quốc hội, kích hoạt FNA). Vì vậy 4 playbook theo loại sự cố ở trên là chuyển thể của tác giả, còn playbook **"Tham chiếu chuẩn: ứng phó sự cố theo CISA (điều chỉnh)"** (31 bước) giữ nguyên thứ tự 11 bước của Phụ lục B (Incident Response Checklist, bản tháng 11/2021), diễn đạt lại bằng tiếng Việt, không dịch từng câu. Mỗi bước ghi mã mục tương ứng trong Phụ lục B ở cuối phần mô tả.

| Bước CISA (Phụ lục B) | Mục | Công việc trong playbook (số thứ tự) | Ghi chú |
| --- | --- | --- | --- |
| 1. Declare Incident | 1a–1c | 1, 2, 3 | 1c chuyển thành báo lãnh đạo và đánh giá nghĩa vụ báo cáo; bỏ 1d (đầu mối liên lạc với CISA) |
| 2. Determine Investigation Scope | 2a–2b | 4 | |
| 3. Collect and Preserve Data | 3a–3b | 5 | Hệ thống tự ghi chain of custody |
| 4. Perform Technical Analysis | 4a–4bb | 6 đến 12 | Gồm ánh xạ ATT&CK (4r–4y) và điều kiện kết thúc phân tích (4d); phần báo cáo cho CISA ở 4c, 4q chuyển thành chia sẻ nội bộ và với đối tác |
| 5. Third-Party Analysis Support | 5a, 5c, 5d | 13 | Bỏ 5b (FNA của liên bang Mỹ) |
| 6. Adjust Tools | 6a–6b | 14 | |
| 7. Contain Activity | 7a–7n | 15 đến 19 | Bỏ 7j (dẫn kẻ tấn công vào sandbox, chỉ cho SOC nâng cao); 7l (báo CISA) chuyển thành cập nhật cho các bên liên quan; biện pháp cụ thể thực hiện ở tab Containment |
| 8. Execute Eradication Plan | 8a–8m | 20 đến 22 | 8b (báo cáo tình trạng cho CISA) chuyển thành cập nhật cho các bên liên quan |
| 9. Recovery (bản gốc đặt trùng tiêu đề với bước 8) | 9a–9l | 23 đến 26 | 9a và 9l trùng nội dung trong bản gốc; chủ hệ thống xác nhận ở tab Recovery |
| 10. Post-Incident Activities | 10a–10r | 29 đến 31 | Bỏ 10g, 10h (báo CISA); 10e chuyển thành đánh giá nghĩa vụ báo cáo |
| 11. Coordination with CISA | 11a–11h | 27, 28 | Chỉ giữ 11d–11f dưới dạng cập nhật nội bộ và chia sẻ với đối tác; bỏ 11a–11c, 11g, 11h |

Phần chuẩn bị trước sự cố (Phụ lục C) không nằm trong playbook này; việc quản lý tài sản, giám sát và nhật ký do các chức năng khác của hệ thống đảm nhiệm. Bảng đối chiếu do tác giả lập từ bản CISA tháng 11/2021 và cần soát lại với bản gốc trước khi nộp. Hệ thống tự thêm playbook tham chiếu vào cơ sở dữ liệu đã có sẵn playbook khác khi khởi động; việc nhận biết dựa trên tên và trường nguồn tham chiếu nên không thêm lại nếu bạn đã đổi tên hoặc ngừng dùng playbook này.

**Áp dụng playbook:** chọn lúc tạo incident (`playbook_id`) hoặc về sau (`POST /incidents/{id}/tasks/apply-playbook`). Áp dụng lại cùng playbook không tạo trùng: bước nào đã có task cùng playbook và cùng tiêu đề trong vụ thì bị bỏ qua. Không áp dụng được cho incident đã đóng. Giao diện gợi ý playbook theo loại triage hoặc tiêu đề của cảnh báo.

**Quyền làm việc:** Analyst giao việc, đặt hạn, tạo hoặc xóa việc thủ công và làm mọi việc. IT/Helpdesk chỉ đổi trạng thái việc giao cho mình hoặc việc chưa giao thuộc vai trò IT; nhận một việc chưa giao thì tự được gán cho người nhận. Stakeholder chỉ xem. Bỏ qua một công việc luôn cần lý do; công việc bắt buộc chỉ commander của vụ được bỏ qua hoặc mở lại. Mở lại việc đã xong cần Analyst và lý do.

**Liên hệ với tiêu chí đóng vụ:** vụ không đóng được khi còn công việc bắt buộc ở trạng thái chưa làm hoặc đang làm. Playbook mẫu đặt bước "viết bản nháp postmortem" là bắt buộc, vì postmortem cần được soạn trước khi đóng, còn việc chốt do commander thực hiện sau khi đóng (xem bước 11). Vì incident đã đóng không nhận thay đổi công việc, các việc sau khi đóng được theo dõi bằng action item của postmortem.

**Giới hạn:** chưa có phụ thuộc giữa các công việc (việc B chỉ mở khi việc A xong), chưa có nhắc việc hoặc leo thang tự động khi quá hạn (chỉ đếm và tô đỏ trên giao diện và dashboard), chưa gắn công việc với từng bước phê duyệt của containment; người xác nhận một công việc đã xong chính là Analyst hoặc commander khi đóng vụ chứ không có bước xác nhận riêng cho từng việc.

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
Containment (executed) → Incident (status: contained) → xác minh (Analyst khác)
    ↓ eradication & recovery (IT) → xác nhận (Stakeholder)
RecoveryAction (is_confirmed: true) → Incident (status: recovering)
    ↓ thông báo (Analyst soạn, Analyst khác duyệt, Stakeholder xác nhận)
Communication (status: acknowledged)
    ↓ đóng incident (commander, đủ tiêu chí đóng)
Incident (status: closed)
    ↓ postmortem (Analyst) → chốt (commander)
Postmortem (is_finalized: true)
    ↓ tự động tính metrics
Dashboard (MTTD, MTTA, MTTR, SLA...)
```

### State machine — Alert

| Trạng thái | Chuyển sang | Điều kiện |
| --- | --- | --- |
| `new` | `reviewing` | Analyst mở xem |
| `new` / `reviewing` | `triaged` | Triage thành công (IT hoặc Analyst) |
| `new` / `reviewing` | `false_positive` | Analyst đánh dấu báo nhầm |
| `triaged` | `escalated` | Tạo incident gộp alert này |
| `escalated` | — | Trạng thái cuối (theo dõi qua incident) |

### State machine — Incident

Chỉ các chuyển trạng thái trong bảng được chấp nhận; mọi chuyển khác bị từ chối (HTTP 400).

| Từ | Sang | Điều kiện |
| --- | --- | --- |
| `open` | `investigating` | Analyst |
| `investigating` | `contained` | Có ít nhất một containment đã thực hiện (hệ thống tự chuyển khi thực hiện containment) |
| `contained` | `recovering` | Có hành động recovery (hệ thống tự chuyển khi mọi hành động đã xong được xác nhận) |
| `contained` / `recovering` | `closed` | Commander của vụ, và đủ tiêu chí đóng (xem bước 11) |
| `contained` / `recovering` | `investigating` | Quay lại điều tra, bắt buộc ghi lý do |
| `closed` | `investigating` | Commander mở lại, bắt buộc ghi lý do |

### State machine — Containment

| Trạng thái | Chuyển sang | Điều kiện |
| --- | --- | --- |
| `proposed` | `approved` | Analyst khác người đề xuất; rủi ro cao chỉ commander |
| `proposed` | `rejected` | Analyst từ chối |
| `approved` | `executed` | IT hoặc Analyst thực hiện (chỉ ghi nhận) |
| `executed` | `verified` | Analyst khác người thực hiện xác minh |

### State machine — Evidence

| Trạng thái | Chuyển sang | Điều kiện |
| --- | --- | --- |
| `is_locked: false` | `is_locked: true` | IT hoặc Analyst khóa |
| `is_locked: true` | — | Không thể sửa sau khi khóa; mỗi lần thu thập, xem, khóa đều ghi vào chain of custody |

### State machine — Recovery check

| Trạng thái | Chuyển sang | Điều kiện |
| --- | --- | --- |
| `pending` | `in_progress` | IT hoặc Analyst bắt đầu (chỉ tạo được sau khi incident đã khống chế) |
| `in_progress` | `done` / `failed` | IT hoặc Analyst cập nhật |
| `done` | `is_confirmed: true` | Chủ hệ thống (stakeholder) xác nhận |

### State machine — Communication

| Trạng thái | Chuyển sang | Điều kiện |
| --- | --- | --- |
| `draft` | `draft` (đã duyệt) | Analyst khác người soạn duyệt; ra ngoài hoặc leo thang cần commander |
| `draft` (đã duyệt) | `sent` | Analyst gửi |
| `sent` | `acknowledged` | Stakeholder xác nhận đã nhận |

### State machine — Công việc (task)

| Trạng thái | Chuyển sang | Điều kiện |
| --- | --- | --- |
| `todo` | `in_progress` | IT hoặc Analyst bắt đầu; IT chỉ với việc giao cho mình hoặc việc chưa giao thuộc IT (việc chưa giao thì gán cho người nhận) |
| `todo` / `in_progress` | `done` | Như trên; ghi người hoàn thành và thời điểm |
| `in_progress` | `todo` | Trả lại việc |
| `todo` / `in_progress` | `skipped` | Chỉ Analyst, bắt buộc có lý do; việc bắt buộc chỉ commander |
| `done` | `in_progress` | Chỉ Analyst, bắt buộc có lý do |
| `skipped` | `todo` | Chỉ Analyst; việc bắt buộc chỉ commander |

Incident đã đóng không nhận thay đổi công việc (409).

### State machine — Postmortem và action item

| Trạng thái | Chuyển sang | Điều kiện |
| --- | --- | --- |
| chưa có | đang soạn | Analyst viết khi incident đang phục hồi hoặc đã đóng |
| đang soạn | `is_finalized: true` | Commander chốt khi incident đã đóng và có ít nhất một action item |
| action item `done: false` | `done: true` | IT hoặc Analyst đánh dấu; tính vào chỉ số hoàn thành |

Đối tượng **approval** của state machine tối thiểu không tách thành bảng riêng: việc phê duyệt được ghi ngay trên containment (người duyệt, thời điểm, kết quả) và trên thông báo (người duyệt), cùng nhật ký kiểm toán. Checklist 5 dòng mặc định của incident vẫn tồn tại để tương thích, nhưng công việc có người phụ trách, hạn và trạng thái là đối tượng task ở trên.

## Nhật ký kiểm toán (audit log)

Mọi thay đổi dữ liệu nghiệp vụ và mọi sự kiện đăng nhập được ghi tự động vào bảng `audit_log`. Các đối tượng được theo dõi: tài sản, alert, incident, bằng chứng, chain of custody, phân tích phạm vi, containment, recovery, thông báo, postmortem, công việc, playbook, cùng đăng nhập, đăng nhập sai, khóa tài khoản và cấp tài khoản.

- **Ghi tự động ở tầng dữ liệu:** một bộ lắng nghe trên session của SQLAlchemy ghi mỗi lần tạo, sửa, xóa các đối tượng trên, nên không thể quên ghi ở một endpoint nào đó. Mỗi bản ghi có người thực hiện (id, tên, vai trò), thời điểm UTC, hành động (ví dụ `containment.approved`), đối tượng, incident liên quan và chi tiết thay đổi (giá trị cũ và mới).
- **Chỉ thêm vào:** không có endpoint sửa hoặc xóa nhật ký.
- **Phát hiện chỉnh sửa:** mỗi bản ghi chứa mã băm SHA-256 của chính nó và của bản ghi trước. Endpoint `/audit/verify` tính lại toàn bộ chuỗi và báo bản ghi đầu tiên bị sửa hoặc mất.
- **Truy cập:** chỉ Analyst xem và xuất CSV.
- **Timeline** của incident được dựng từ nhật ký (gồm cả các sự kiện của cảnh báo trước khi có incident), nên luôn khớp với nhật ký.

**Hạn chế:** chuỗi băm phát hiện chỉnh sửa nhưng không ngăn được người có quyền quản trị trực tiếp cơ sở dữ liệu; hai thao tác ghi đồng thời có thể làm chuỗi rẽ nhánh; lượt đọc dữ liệu không được ghi (riêng lượt xem bằng chứng được ghi trong chain of custody).

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

**Dữ liệu:** MITRE ATT&CK Enterprise (snapshot tải từ mitre/cti) — 697 techniques (không revoked, không deprecated). Snapshot được định danh bằng ngày sửa đổi mới nhất của dữ liệu (nhãn `ent-YYYY-MM-DD`) và SHA-256 của file, ghi trong `ml/models/attck_version.json`.

**Quy trình:**

1. Mỗi technique tạo một tài liệu gồm: tên (nhân ba trọng số) + mô tả + gợi ý phát hiện + tối đa 40 ví dụ thực tế (procedure examples lấy từ các quan hệ `uses` trong dữ liệu; 611/697 technique có ví dụ, tổng 17,136 ví dụ).
2. Chỉ mục BM25 (k1 = 1.5, b = 0.75), unigram, stop words tiếng Anh.
3. Truy vấn tiếng Việt được dịch cụm từ sang tiếng Anh bằng bảng thuật ngữ an ninh mạng 173 mục (`ml/attck_glossary_vi.json`) trước khi tìm.
4. Reranking: nhân điểm 1.5 nếu tên technique xuất hiện trong truy vấn.
5. Với `/alert/suggest`, IP, email và tên miền (IOC) được loại khỏi truy vấn truy hồi vì chúng mô tả chỉ báo chứ không mô tả hành vi.
6. Trả về Top-K kết quả cùng điểm BM25 (không nằm trong khoảng 0–1).

**Lưu phiên bản:** `models/attck_version.json` ghi nhãn snapshot, SHA-256, số technique, số ví dụ và thời điểm lập chỉ mục. Khi lưu phân tích phạm vi có kỹ thuật ATT&CK mà không nhập phiên bản, backend tự điền nhãn này từ AI service.

### Tích hợp vào hệ thống

Endpoint `/ai/alert/suggest` trong backend nhận title + description + IOC, gọi AI service, trả về:

- `severity_suggestion`: mức độ đề xuất, tính bằng luật từ khóa (tiếng Anh, cùng bản dịch của truy vấn tiếng Việt). Đây không phải đầu ra của mô hình Random Forest.
- `attck_techniques`: Top-5 techniques với id, tên, tactic, điểm BM25
- `summary`: tóm tắt ngắn gọn bằng tiếng Việt
- `ai_generated: true` — đánh dấu rõ nội dung do AI tạo, kèm `generated_by`
- `warning`: nhắc Analyst xác nhận trước khi sử dụng

Mô hình Random Forest phục vụ qua `/classify` của AI service (đầu vào là thuộc tính luồng mạng). Hiện endpoint này chưa được backend hoặc giao diện gọi tới.

**Bảo mật:** Sanitize input trước khi xử lý, giới hạn độ dài 2000 ký tự, từ chối các pattern nguy hiểm. Hệ thống không dùng LLM nên rủi ro prompt injection ở mức thấp; bộ lọc này là lớp phòng vệ bổ sung.

### Kết quả đánh giá

**Bộ phân loại luồng mạng** (tập test 565,576 luồng, 111,311 tấn công; chia ngẫu nhiên 80/20 trên CIC-IDS2017):

| Chỉ số | Giá trị |
| --- | --- |
| PR-AUC / ROC-AUC | 0.9998 / 0.9999 |
| Ngưỡng 0.5: Precision / Recall / F1 | 0.9951 / 0.9993 / 0.9972 |
| Ngưỡng 0.5: False Positive / False Negative | 546 / 82 |
| Vùng tự đóng (prob < 0.15) | 80.07% số luồng, bỏ sót 24 tấn công (0.022%) |
| Recall nhóm mức độ cao, gộp theo số mẫu | 0.9991 |
| Recall nhóm mức độ cao, trung bình đều theo lớp | khoảng 0.948 (Bot 0.873; Infiltration 0.667 với n = 6) |

Kết quả có thể cao hơn thực tế do cách chia ngẫu nhiên (các luồng gần giống nhau có thể nằm ở cả hai tập). Các lớp hiếm (Heartbleed n = 2, SQL Injection n = 2, Infiltration n = 6) không đủ mẫu để kết luận theo từng lớp.

**Ánh xạ ATT&CK** (tập giữ lại 29 mô tả, viết và đóng băng trước khi cải tiến; Top-K tính theo ID chính xác):

| Truy vấn | Phương pháp | Top-1 | Top-3 | Top-5 | MRR |
| --- | --- | --- | --- | --- | --- |
| Tiếng Anh | TF-IDF (trước) | 51.7% | 72.4% | 79.3% | 0.630 |
| Tiếng Anh | BM25 + ví dụ thực tế | 62.1% | 79.3% | 82.8% | 0.709 |
| Tiếng Việt | TF-IDF (trước) | 24.1% | 34.5% | 34.5% | 0.292 |
| Tiếng Việt | BM25 + ví dụ + bảng thuật ngữ | 58.6% | 72.4% | 82.8% | 0.675 |

Với n = 29, khoảng tin cậy 95% của Top-5 tiếng Anh chồng lấn giữa hai phương pháp nên mức cải thiện này chưa đủ để khẳng định; mức cải thiện tiếng Việt thì rõ ràng. Nhãn và các câu mô tả do tác giả xây dựng.

**Gom nhóm cảnh báo** (tập mô phỏng 102 cảnh báo, 39 sự cố; luật: cùng IOC chuẩn hóa, cùng tài sản, trong cửa sổ 60 phút):

| Chỉ số | Giá trị |
| --- | --- |
| Precision / Recall / F1 theo cặp | 91.3% / 68.3% / 78.1% |
| Sự cố được gom trọn vẹn | 16/25 |

Luật hoạt động tốt khi cảnh báo có cùng IOC và cùng tài sản. Luật không gom được trong các trường hợp: sự cố lan sang nhiều tài sản, cảnh báo thiếu IOC, IOC chồng lấn một phần, khoảng cách giữa hai cảnh báo lớn hơn 60 phút.

**Kiểm thử khói (smoke benchmark) của luồng triage:** `tests/benchmark_ai.py` chạy 7 cảnh báo mô phỏng. Nhãn mong đợi và giá trị `manual_guess` do tác giả gán thủ công, và luật từ khóa của AI trùng với từ khóa trong tiêu đề các cảnh báo thử. Vì vậy các con số (28.6% so với 85.7%) chỉ minh họa luồng chạy, không dùng làm bằng chứng AI cải thiện chất lượng triage. Chỉ số đo được đáng tin cậy duy nhất của benchmark này là độ trễ: gọi AI làm thời gian triage tăng thêm khoảng 2.45 giây. Đánh giá thời gian triage của analyst có/không có AI cần thử nghiệm với người dùng thật.

## API Endpoints chính

Base URL: `http://localhost:8000` | Docs: `http://localhost:8000/docs`

### Auth

| Method | Endpoint | Mô tả | Role |
| --- | --- | --- | --- |
| POST | `/auth/register` | Tạo tài khoản (tài khoản đầu tiên tạo tự do, sau đó chỉ Analyst) | Analyst |
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
| PATCH | `/incidents/{id}/status` | Đổi trạng thái theo bảng hợp lệ; đóng và mở lại chỉ commander | Analyst |
| GET | `/incidents/{id}/alerts` | Alerts thuộc incident | All |
| GET | `/incidents/{id}/timeline` | Timeline dựng từ nhật ký kiểm toán | All |

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
| PATCH | `/incidents/{id}/containments/{cid}/review` | Phê duyệt (khác người đề xuất; rủi ro cao: commander) | Analyst |
| PATCH | `/incidents/{id}/containments/{cid}/execute` | Thực hiện | IT, Analyst |
| PATCH | `/incidents/{id}/containments/{cid}/verify` | Xác minh (khác người thực hiện) | Analyst |
| POST | `/incidents/{id}/recovery/` | Tạo recovery action | IT, Analyst |
| PATCH | `/incidents/{id}/recovery/{rid}/confirm` | Xác nhận recovery | Stakeholder |
| POST | `/incidents/{id}/communications/` | Tạo thông báo | Analyst |
| PATCH | `/incidents/{id}/communications/{cid}/approve` | Phê duyệt (khác người soạn; ra ngoài: commander) | Analyst |
| PATCH | `/incidents/{id}/communications/{cid}/send` | Gửi | Analyst |
| PATCH | `/incidents/{id}/communications/{cid}/acknowledge` | Xác nhận đã nhận | Stakeholder |
| POST | `/incidents/{id}/postmortem/` | Viết postmortem | Analyst |
| PATCH | `/incidents/{id}/postmortem/finalize` | Chốt postmortem (incident đã đóng, commander) | Analyst |

### Playbook và công việc

| Method | Endpoint | Mô tả | Role |
| --- | --- | --- | --- |
| GET | `/playbooks/` | Danh sách (lọc `incident_type`, `active_only`) | All |
| GET | `/playbooks/{id}` | Chi tiết kèm các bước | All |
| POST | `/playbooks/` | Tạo playbook | Analyst |
| PUT | `/playbooks/{id}` | Sửa, thay toàn bộ bước, ngừng dùng | Analyst |
| GET | `/incidents/{id}/tasks/` | Danh sách công việc của vụ | All |
| GET | `/incidents/{id}/tasks/summary` | Tổng hợp: số việc, bắt buộc chưa xong, quá hạn, % xử lý | All |
| GET | `/incidents/{id}/tasks/assignees` | Tài khoản có thể được giao việc | Analyst |
| POST | `/incidents/{id}/tasks/apply-playbook` | Tạo công việc từ playbook, không tạo trùng | Analyst |
| POST | `/incidents/{id}/tasks/` | Tạo công việc thủ công | Analyst |
| PATCH | `/incidents/{id}/tasks/{tid}` | Đổi trạng thái; giao việc, đặt hạn (chỉ Analyst) | IT, Analyst |
| DELETE | `/incidents/{id}/tasks/{tid}` | Xóa việc thủ công chưa xong | Analyst |

### Audit

| Method | Endpoint | Mô tả | Role |
| --- | --- | --- | --- |
| GET | `/audit/` | Danh sách, lọc theo incident, người dùng, hành động, đối tượng, thời gian | Analyst |
| GET | `/audit/verify` | Kiểm tra toàn vẹn chuỗi băm | Analyst |
| GET | `/audit/export.csv` | Xuất CSV | Analyst |

### Dashboard & AI

| Method | Endpoint | Mô tả | Role |
| --- | --- | --- | --- |
| GET | `/dashboard/` | 6 chỉ số + stats + thống kê công việc đang mở và quá hạn | All |
| GET | `/dashboard/sla` | Alerts vi phạm SLA | All |
| POST | `/ai/alert/suggest` | AI đề xuất severity + ATT&CK | All |
| POST | `/ai/attck/search` | Tìm kiếm ATT&CK techniques | All |
| GET | `/ai/health` | Kiểm tra AI service | All |