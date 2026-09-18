# Đề tài: Hệ thống quản lý sự cố an ninh mạng cho tổ chức vừa và nhỏ tích hợp AI phân loại cảnh báo


## Bối cảnh và giá trị ứng dụng

NIST SP 800-61 Revision 3, phát hành chính thức tháng 4/2025, đưa ứng phó sự cố vào toàn bộ hoạt động quản trị rủi ro và nhấn mạnh các chức năng Detect, Respond và Recover trong mối liên hệ với CSF 2.0. Đối với doanh nghiệp nhỏ, một hệ thống gọn nhẹ có thể giúp chuẩn hóa tiếp nhận cảnh báo, phân công điều tra, lưu bằng chứng, phê duyệt hành động, phục hồi và postmortem mà không cần xây dựng đầy đủ một SIEM thương mại.

## Các nhóm người dùng

- **IT/Helpdesk** — tiếp nhận báo cáo nghi ngờ từ nhân viên, nhập cảnh báo ban đầu vào hệ thống và chuyển cho SOC xử lý.
- **Analyst/SOC** — thực hiện triage, điều tra, phân tích kỹ thuật, phê duyệt hành động containment và đóng vụ việc.
- **Stakeholder** — xem báo cáo tóm tắt, xác nhận khôi phục hệ thống và xuất audit log/chain of custody khi cần.

## Quy trình nghiệp vụ chính cần cài đặt

1. Quản lý tài sản và mức quan trọng: máy chủ, ứng dụng, tài khoản, chủ sở hữu, dữ liệu xử lý, phụ thuộc và mức ảnh hưởng.
2. Tiếp nhận cảnh báo: API/webhook/tệp từ IDS, email nghi phishing, cảnh báo endpoint hoặc báo cáo thủ công.
3. Chuẩn hóa và chống trùng: chuẩn hóa trường, gom các cảnh báo cùng IOC/tài sản/thời gian, giữ liên kết về nguồn.
4. Triage: xác định loại, mức độ, độ tin cậy, tài sản ảnh hưởng, người phụ trách và SLA.
5. Tạo vụ việc: chuyển một hoặc nhiều cảnh báo thành incident, chỉ định incident commander và checklist ban đầu.
6. Thu thập bằng chứng: log, email, hash, ảnh màn hình, timeline, nguồn thu và chain of custody.
7. Phân tích và phạm vi ảnh hưởng: liên kết IOC, tài sản, tài khoản, kỹ thuật tấn công và các sự kiện liên quan.
8. Containment: đề xuất hành động như khóa tài khoản, cô lập máy, chặn IOC; yêu cầu phê duyệt theo mức rủi ro và ghi bằng chứng thực hiện.
9. Eradication và Recovery: loại bỏ nguyên nhân, vá lỗi, khôi phục, kiểm tra lại, tăng giám sát và xác nhận chủ hệ thống.
10. Thông báo và phối hợp: mẫu cập nhật nội bộ, danh sách bên liên quan, lịch sử thông báo và nội dung đã phê duyệt.
11. Đóng vụ việc và postmortem: nguyên nhân gốc, timeline, tác động, bài học, hành động phòng ngừa, người chịu trách nhiệm và thời hạn.
12. Đo lường: MTTD, MTTA, MTTR, số vụ mở, lỗi lặp, SLA và mức hoàn thành hành động sau sự cố.

## Mô-đun ML/AI chính — Phân loại và ưu tiên cảnh báo đa nguồn

Đầu vào: thuộc tính luồng mạng, nội dung email/báo cáo, IOC, tài sản và ngữ cảnh tổ chức.

Đầu ra: loại cảnh báo, xác suất độc hại, mức ưu tiên đề xuất, các đặc trưng chính và liên kết cảnh báo tương tự.

Gợi ý thiết kế:
- Baseline cho dữ liệu mạng: Logistic Regression/Random Forest.
- Baseline cho email: TF-IDF + Linear SVM.
- Mô hình chính: Gradient Boosting cho đặc trưng có cấu trúc; transformer cho nội dung; hợp nhất điểm với mức quan trọng của tài sản và độ tin cậy nguồn.
- Tối ưu theo precision-recall thay vì accuracy vì dữ liệu cảnh báo thường mất cân bằng.
- Thiết lập ngưỡng ba vùng: tự đóng theo luật an toàn, cần analyst xem, ưu tiên khẩn. Trong luận văn, không tự động thực thi containment trên hệ thống thật.

### Các ý tưởng AI mở rộng

- Phân loại email phishing và trích xuất URL/domain/đối tượng bị mạo danh.
- Gom cụm cảnh báo thành incident bằng similarity và cửa sổ thời gian.
- Phát hiện bất thường log bằng autoencoder hoặc mô hình chuỗi.
- Ánh xạ mô tả sự cố sang MITRE ATT&CK bằng retrieval + reranking.
- RAG tạo bản tóm tắt điều hành hoặc bản nháp postmortem dựa trên timeline đã xác minh; mọi câu phải có liên kết đến bằng chứng/bản ghi nguồn.
- Gợi ý playbook theo loại sự cố, nhưng hành động phải được con người phê duyệt.

## Dữ liệu và cách xây dựng dữ liệu

- CIC-IDS2017 hoặc bộ dữ liệu IDS khác từ Canadian Institute for Cybersecurity.
- SpamAssassin public corpus cho baseline email spam/phishing; cần bổ sung dữ liệu phishing hiện đại hoặc mẫu mô phỏng an toàn.
- MITRE ATT&CK STIX/TAXII.
- Tạo lab cô lập bằng máy ảo/container để sinh log tấn công phòng thủ cơ bản; không dùng hạ tầng bên ngoài hoặc dữ liệu không được phép.
- Dữ liệu incident workflow được mô phỏng với các ca phishing, credential compromise, malware và web attack.

## Phạm vi MVP phù hợp

- Web quản lý tài sản, cảnh báo, incident, bằng chứng, task, phê duyệt, phục hồi và postmortem.
- Nhập cảnh báo từ CSV/JSON/webhook mô phỏng.
- Một mô hình phân loại cảnh báo hoặc phishing; ánh xạ ATT&CK bằng retrieval.
- Dashboard SLA và timeline; chưa cần tích hợp tự động với firewall/EDR thật.

## Tiêu chí đánh giá

- PR-AUC, recall nhóm mức độ cao, precision tại ngưỡng vận hành và ma trận nhầm lẫn.
- Thời gian triage trong thử nghiệm analyst có/không có AI.
- Tỷ lệ gom đúng cảnh báo cùng incident.
- Độ chính xác Top-K của ánh xạ ATT&CK.
- Groundedness của tóm tắt: tỷ lệ câu có bằng chứng hỗ trợ, số chi tiết bịa đặt và mức chỉnh sửa của analyst.
- Kiểm thử phân quyền, chain of custody và audit log.

## Rủi ro cần kiểm soát

Mọi thử nghiệm phải nằm trong môi trường được phép và cô lập. Không tự động vô hiệu hóa tài khoản hoặc chặn hệ thống thật. Cần chống prompt injection trong dữ liệu log/email khi dùng LLM, lọc bí mật trước khi gửi mô hình bên ngoài và đánh dấu rõ nội dung do AI tạo.

## Tài liệu tham khảo nghiệp vụ cốt lõi

| Mã | Tài liệu | Các bước hỗ trợ |
|---|---|---|
| BP10.1 | NIST SP 800-61 Rev.3 - Incident Response Recommendations and Considerations for Cybersecurity Risk Management | Bước 1-12 |
| BP10.2 | CISA - Federal Government Cybersecurity Incident and Vulnerability Response Playbooks | Bước 2-5 và 7-11 |
| BP10.3 | FIRST - CSIRT Services Framework Version 2.1 | Bước 2-12 |
| BP10.4 | NIST SP 800-86 - Guide to Integrating Forensic Techniques into Incident Response | Bước 6, 7, 9 và 11 |
| BP10.5 | MITRE ATT&CK - ATT&CK Data and Tools | Bước 7, 9 và 11 |