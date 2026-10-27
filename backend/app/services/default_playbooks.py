from sqlalchemy.orm import Session

from app.models.user import RoleEnum
from app.models.playbook import Playbook, PlaybookStep, PlaybookType, TaskPhase

IT = RoleEnum.it_helpdesk
AN = RoleEnum.analyst_soc
P = TaskPhase

SOURCE = ("Xây dựng dựa trên CISA Federal Government Cybersecurity Incident and Vulnerability Response "
          "Playbooks và NIST SP 800-61 Rev. 3; điều chỉnh cho tổ chức vừa và nhỏ.")

# (tiêu đề, mô tả, giai đoạn, vai trò thường đảm nhiệm, hạn (giờ), bắt buộc)
DEFAULTS = [
    {
        "name": "Phishing qua email",
        "incident_type": PlaybookType.phishing,
        "description": "Email nghi ngờ lừa đảo được người dùng báo cáo hoặc hệ thống lọc thư phát hiện.",
        "steps": [
            ("Thu nhận email gốc", "Lấy thư nguyên bản kèm header đầy đủ (.eml hoặc chuyển tiếp dạng tệp đính kèm). Không để người dùng xóa thư.", P.analysis, IT, 1, True),
            ("Phân tích header, URL và tệp đính kèm", "Trích xuất IOC: domain và địa chỉ gửi, URL, hash tệp. Đối chiếu với các cảnh báo đã có.", P.analysis, AN, 2, True),
            ("Thu thập bằng chứng", "Lưu thư gốc, hash tệp đính kèm và ảnh chụp màn hình vào mục bằng chứng để ghi chain of custody.", P.evidence, IT, 4, True),
            ("Xác định người nhận và người đã tương tác", "Liệt kê ai đã nhận, mở tệp, nhấp liên kết hoặc nhập thông tin vào trang giả mạo.", P.analysis, AN, 4, True),
            ("Đề xuất chặn và thu hồi thư", "Đề xuất containment: chặn domain hoặc địa chỉ gửi, thu hồi thư khỏi hộp thư người nhận.", P.containment, IT, 4, True),
            ("Đặt lại mật khẩu tài khoản bị lộ", "Với tài khoản đã nhập thông tin vào trang giả mạo: đặt lại mật khẩu và thu hồi phiên đăng nhập.", P.recovery, IT, 8, True),
            ("Quét máy của người đã mở tệp đính kèm", "Quét và xác nhận không có mã độc trên máy; nếu có, chuyển sang playbook mã độc.", P.recovery, IT, 24, True),
            ("Thông báo người nhận và phòng ban liên quan", "Thông báo nội bộ và nhắc nhở nhận biết phishing.", P.communication, AN, 24, False),
            ("Viết bản nháp postmortem", "Nguyên nhân gốc, timeline, tác động, bài học. Commander chốt sau khi đóng vụ.", P.closure, AN, 72, True),
        ],
    },
    {
        "name": "Lạm dụng tài khoản (credential compromise)",
        "incident_type": PlaybookType.credential_compromise,
        "description": "Tài khoản có dấu hiệu bị chiếm quyền: đăng nhập bất thường, nhiều lần thất bại rồi thành công.",
        "steps": [
            ("Xác nhận dấu hiệu lạm dụng", "Đối chiếu đăng nhập bất thường về địa lý, thời gian, thiết bị lạ.", P.analysis, AN, 1, True),
            ("Xác định tài khoản và quyền truy cập bị ảnh hưởng", "Ghi các tài khoản liên quan và hệ thống, dữ liệu mà chúng truy cập được.", P.analysis, AN, 2, True),
            ("Thu thập log xác thực", "Log đăng nhập, đổi mật khẩu, phiên làm việc của tài khoản trong khung giờ liên quan.", P.evidence, IT, 4, True),
            ("Rà soát hành vi sau khi đăng nhập", "Truy cập dữ liệu, thay đổi quyền, tạo quy tắc chuyển tiếp thư, đăng nhập sang hệ thống khác.", P.analysis, AN, 4, True),
            ("Đề xuất khóa tài khoản và thu hồi phiên", "Đề xuất containment: khóa hoặc đặt lại tài khoản, thu hồi phiên và token đang hoạt động.", P.containment, IT, 2, True),
            ("Đặt lại thông tin xác thực, bật MFA", "Đặt lại mật khẩu và bật xác thực đa yếu tố cho tài khoản bị ảnh hưởng.", P.recovery, IT, 8, True),
            ("Gỡ quyền và cấu hình do kẻ tấn công thêm", "Quy tắc chuyển tiếp thư, thiết bị tin cậy, khóa API hoặc quyền được thêm trái phép.", P.recovery, IT, 24, True),
            ("Thông báo chủ tài khoản và quản lý trực tiếp", "Giải thích sự việc và việc cần làm tiếp theo.", P.communication, AN, 24, False),
            ("Viết bản nháp postmortem", "Nguyên nhân gốc (mật khẩu yếu, phishing, tái sử dụng mật khẩu...), timeline, bài học.", P.closure, AN, 72, True),
        ],
    },
    {
        "name": "Mã độc trên máy trạm hoặc máy chủ",
        "incident_type": PlaybookType.malware,
        "description": "Cảnh báo mã độc từ endpoint, hoặc tiến trình và kết nối đáng ngờ trên máy.",
        "steps": [
            ("Xác nhận cảnh báo và xác định máy bị nhiễm", "Đối chiếu cảnh báo với dữ liệu trên máy; ghi tên máy, người dùng, thời điểm.", P.analysis, AN, 1, True),
            ("Thu thập bằng chứng", "Hash mẫu, danh sách tiến trình, kết nối mạng, bản chụp bộ nhớ nếu có. Làm việc trên bản sao, không phân tích trên bản gốc.", P.evidence, IT, 2, True),
            ("Phân tích mẫu trong môi trường cô lập", "Xác định IOC và kỹ thuật ATT&CK; ghi vào phân tích phạm vi.", P.analysis, AN, 4, True),
            ("Xác định phạm vi lây lan", "Tìm máy khác có cùng IOC và tài khoản đã đăng nhập trên máy bị nhiễm.", P.analysis, AN, 6, True),
            ("Đề xuất cô lập máy và chặn IOC", "Đề xuất containment: cô lập máy khỏi mạng, chặn IP, domain, hash.", P.containment, IT, 2, True),
            ("Loại bỏ mã độc và vá lỗ hổng", "Loại bỏ mã độc, vá lỗ hổng hoặc cấu hình sai đã bị khai thác.", P.recovery, IT, 24, True),
            ("Đặt lại mật khẩu các tài khoản đã dùng trên máy", "Bao gồm tài khoản dịch vụ và tài khoản quản trị nếu có.", P.recovery, IT, 24, True),
            ("Khôi phục từ bản sao lưu sạch hoặc dựng lại máy", "Kiểm tra lại sau khôi phục và tăng giám sát trong thời gian đầu.", P.recovery, IT, 48, True),
            ("Thông báo chủ hệ thống và lãnh đạo", "Tác động, kế hoạch khôi phục và thời gian dự kiến.", P.communication, AN, 24, False),
            ("Viết bản nháp postmortem", "Nguyên nhân gốc, timeline, tác động, bài học và hành động phòng ngừa.", P.closure, AN, 72, True),
        ],
    },
    {
        "name": "Tấn công ứng dụng web",
        "incident_type": PlaybookType.web_attack,
        "description": "SQL injection, XSS, thực thi mã từ xa hoặc quét lỗ hổng nhằm vào ứng dụng web.",
        "steps": [
            ("Xác nhận tấn công và phân loại", "Đối chiếu log web server hoặc WAF, xác định loại tấn công và có thành công hay không.", P.analysis, AN, 1, True),
            ("Thu thập log truy cập, WAF, ứng dụng và cơ sở dữ liệu", "Trong khung giờ liên quan; lưu hash và nguồn vào mục bằng chứng.", P.evidence, IT, 2, True),
            ("Xác định lỗ hổng bị khai thác và dữ liệu bị ảnh hưởng", "Ghi điểm yếu, endpoint và dữ liệu có thể bị truy cập hoặc thay đổi.", P.analysis, AN, 4, True),
            ("Đề xuất chặn nguồn tấn công", "Đề xuất containment: chặn IP, bật quy tắc WAF hoặc tạm ngừng chức năng bị ảnh hưởng.", P.containment, IT, 2, True),
            ("Kiểm tra webshell và thay đổi trái phép", "Tệp mới hoặc bị sửa, tài khoản mới, tác vụ định kỳ lạ trên máy chủ.", P.analysis, AN, 8, True),
            ("Vá hoặc sửa mã ứng dụng, cập nhật cấu hình", "Kiểm thử lại để xác nhận lỗ hổng đã được đóng.", P.recovery, IT, 24, True),
            ("Khôi phục dữ liệu bị thay đổi và xác nhận với chủ ứng dụng", "Đối chiếu với bản sao lưu; chủ ứng dụng xác nhận.", P.recovery, IT, 48, True),
            ("Đánh giá nghĩa vụ thông báo", "Nếu dữ liệu cá nhân hoặc khách hàng bị ảnh hưởng, trao đổi với pháp chế về thông báo.", P.communication, AN, 24, False),
            ("Viết bản nháp postmortem", "Nguyên nhân gốc, timeline, tác động, bài học và hành động phòng ngừa.", P.closure, AN, 72, True),
        ],
    },
]


# ── Playbook tham chiếu chuẩn ──────────────────────────────────────────────
# Giữ cấu trúc 11 bước của CISA Incident Response Checklist (Phụ lục B), diễn đạt lại bằng tiếng Việt
# và điều chỉnh cho tổ chức vừa và nhỏ. Mã tham chiếu ghi ở cuối mô tả của từng bước.
REF_SOURCE = ("CISA Federal Government Cybersecurity Incident and Vulnerability Response Playbooks (11/2021), "
              "Phụ lục B (Incident Response Checklist); NIST SP 800-61 Rev. 3; NIST SP 800-86.")

REF_DESCRIPTION = (
    "Playbook đối chiếu với checklist ứng phó sự cố của CISA, dùng làm chuẩn tham chiếu khi cần kiểm tra quy trình đã đủ bước hay chưa. "
    "Giữ thứ tự các bước 1 đến 11 của bản gốc, diễn đạt lại bằng tiếng Việt, không phải bản dịch từng câu. "
    "Điều chỉnh cho tổ chức vừa và nhỏ: bỏ các mục chỉ áp dụng cho cơ quan liên bang Mỹ hoặc SOC nâng cao (1d, 5b, 7j, 10g, 10h, 11a đến 11c, 11g, 11h); "
    "chuyển thể các mục báo cáo cho CISA thành thông báo nội bộ và cho đối tác (1c, 8b, 10e, 11d đến 11f). "
    "Phần chuẩn bị trước sự cố (Phụ lục C) không nằm trong playbook này. Mỗi bước có mã tham chiếu mục tương ứng trong Phụ lục B."
)

REF_STEPS = [
    ("Phân loại sơ bộ sự cố và xác nhận commander", "Phân loại sơ bộ theo loại và mức độ; xác nhận người điều phối (commander) của vụ.", P.analysis, AN, 1, True, "1a–1b"),
    ("Báo lãnh đạo và bộ phận CNTT về sự cố", "Thông báo cho lãnh đạo, quản lý CNTT và chủ hệ thống bị ảnh hưởng. Bản gốc yêu cầu báo CISA; bước này thay bằng thông báo nội bộ.", P.communication, AN, 2, True, "1c (chuyển thể)"),
    ("Đánh giá nghĩa vụ báo cáo cơ quan chức năng hoặc đối tác", "Xem xét nghĩa vụ báo cáo theo quy định hiện hành hoặc hợp đồng (trao đổi pháp chế nếu có) và nhu cầu phối hợp với cơ quan thực thi pháp luật.", P.communication, AN, 24, False, "1c, 10e (chuyển thể)"),
    ("Xác định loại và mức độ ảnh hưởng của sự cố", "Xác định loại, phạm vi ban đầu và tác động tới hoạt động nghiệp vụ hoặc thông tin.", P.analysis, AN, 2, True, "2a–2b"),
    ("Thu thập và bảo toàn dữ liệu làm bằng chứng", "Thu thập dữ liệu phục vụ xác minh, phân loại, ưu tiên, khắc phục, báo cáo và làm bằng chứng. Ghi cách thu, thời điểm thu và người thu; hệ thống tự ghi chain of custody khi tạo mục bằng chứng.", P.evidence, IT, 4, True, "3a–3b; NIST SP 800-86"),
    ("Phân tích kỹ thuật và lập giả thuyết về mục tiêu của kẻ tấn công", "Xây dựng hiểu biết kỹ thuật và bối cảnh về sự cố; dựa trên phân tích và thông tin đe dọa để lập giả thuyết về điều kẻ tấn công muốn đạt được; cập nhật phạm vi khi có thông tin mới.", P.analysis, AN, 6, True, "4a–4c"),
    ("Đối chiếu log và dựng timeline sự cố", "Ghi sự kiện, mô tả, thời điểm (giờ UTC), tác động và nguồn dữ liệu; cập nhật liên tục. Timeline của vụ được dựng từ nhật ký kiểm toán.", P.analysis, AN, 8, True, "4e–4f"),
    ("Tìm hoạt động bất thường so với baseline", "Rà soát hệ thống và mạng bị ảnh hưởng; chú ý trường hợp kẻ tấn công dùng tài khoản hợp lệ và công cụ sẵn có của hệ điều hành.", P.analysis, AN, 8, False, "4g–4h"),
    ("Xác định nguyên nhân gốc, vector tấn công và mức độ truy cập", "Xác định nguyên nhân gốc và điều kiện cho phép kẻ tấn công vào hệ thống; vector tấn công (mã độc, RDP, VPN...); các hệ thống, tài khoản, dịch vụ và mạng bị chạm tới; thay đổi dùng để né tránh hoặc duy trì truy cập.", P.analysis, AN, 12, True, "4i–4m"),
    ("Thu thập chỉ số xâm phạm (IOC) và đối chiếu thông tin đe dọa", "Ghi IOC vào bản phân tích phạm vi; đối chiếu thông tin về hoạt động tương tự; phân tích công cụ của kẻ tấn công để rút IOC; chia sẻ cho các nhóm ứng phó nội bộ.", P.analysis, AN, 8, True, "4n–4q"),
    ("Ánh xạ hành vi tấn công sang MITRE ATT&CK", "Xác định truy cập ban đầu, điều khiển từ xa (C2), thực thi mã, duy trì truy cập, di chuyển ngang, đánh cắp thông tin xác thực hoặc leo thang đặc quyền, rò rỉ dữ liệu. Dùng chức năng ánh xạ ATT&CK ở mục Phạm vi.", P.analysis, AN, 12, True, "4r–4y"),
    ("Xác nhận và điều chỉnh lại phạm vi điều tra", "Tìm hệ thống, thiết bị, tài khoản bị ảnh hưởng thêm; đưa IOC mới vào công cụ phát hiện; thông báo phạm vi mới cho các bên liên quan. Phân tích xong khi sự cố đã được xác minh, phạm vi và cách duy trì truy cập đã rõ, tác động đã đánh giá và mọi bên cùng thống nhất bức tranh hiện tại.", P.analysis, AN, 16, True, "4d, 4z–4bb"),
    ("Đánh giá nhu cầu hỗ trợ từ bên ngoài", "Cân nhắc nhờ đơn vị ứng cứu hoặc nhà cung cấp dịch vụ; phối hợp truy cập và làm việc với nhà cung cấp lưu trữ hệ thống bên ngoài.", P.analysis, AN, 8, False, "5a, 5c–5d"),
    ("Điều chỉnh công cụ phát hiện và ngăn chặn theo IOC và kỹ thuật đã biết", "Tinh chỉnh công cụ để làm chậm kẻ tấn công và giảm thời gian chúng ẩn náu, tập trung vào các kỹ thuật bắt buộc phải dùng (thực thi, đánh cắp thông tin xác thực, di chuyển ngang).", P.analysis, IT, 12, False, "6a–6b"),
    ("Chọn chiến lược ngăn chặn", "Cân nhắc nhu cầu bảo toàn bằng chứng, tính sẵn sàng của dịch vụ, nguồn lực hiện có và thời gian thực hiện từng bước.", P.containment, AN, 4, True, "7a"),
    ("Sao lưu hoặc tạo bản sao hệ thống bị ảnh hưởng trước khi xử lý", "Bảo toàn bằng chứng và phục vụ điều tra tiếp. Phối hợp cơ quan thực thi pháp luật nếu cần trước khi loại bỏ.", P.evidence, IT, 4, True, "7b–7c"),
    ("Đề xuất và thực hiện biện pháp ngăn chặn", "Cô lập hệ thống hoặc đoạn mạng, đóng cổng và cập nhật tường lửa, đổi mật khẩu quản trị và khóa bí mật bị nghi lộ, chặn IP và domain độc hại, chặn kết nối ra ngoài, ngăn máy bị ảnh hưởng nối sang máy khác. Đề xuất, phê duyệt và xác minh ở tab Containment.", P.containment, IT, 6, True, "7d–7i"),
    ("Theo dõi phản ứng của kẻ tấn công và quay lại phân tích nếu có dấu hiệu mới", "Nếu phát hiện dấu hiệu xâm phạm mới, quay lại bước phân tích kỹ thuật để xác định lại phạm vi; cập nhật timeline và phát hiện mới cho các bên liên quan.", P.containment, AN, 24, True, "7k–7m"),
    ("Xác nhận đã ngăn chặn thành công", "Không còn dấu hiệu xâm phạm mới; bảo toàn bằng chứng; điều chỉnh công cụ phát hiện; chuyển sang loại bỏ.", P.containment, AN, 24, True, "7n"),
    ("Lập kế hoạch loại bỏ nguyên nhân", "Tính đến nhiều cơ chế duy trì truy cập và vector tấn công thay thế mà kẻ tấn công có thể dùng.", P.recovery, AN, 24, True, "8a"),
    ("Loại bỏ dấu vết sự cố", "Xóa mã độc và tệp liên quan, dựng lại hệ thống từ nguồn sạch, thay phần cứng nếu có rootkit, quét lại để xác nhận đã sạch.", P.recovery, IT, 48, True, "8c–8f"),
    ("Giám sát tái xâm nhập sau khi loại bỏ", "Theo dõi phản ứng của kẻ tấn công và dành đủ thời gian để chắc chắn không còn cơ chế duy trì truy cập. Nếu có hoạt động mới thì ngăn chặn rồi quay lại phân tích.", P.recovery, AN, 72, True, "8g–8m"),
    ("Khôi phục hệ thống và dữ liệu nghiệp vụ", "Đưa hệ thống trở lại vận hành, khôi phục dữ liệu nghiệp vụ, hoàn tác các thay đổi tạm thời đã làm trong lúc ứng phó. Chủ hệ thống xác nhận ở tab Recovery.", P.recovery, IT, 72, True, "9a–9b, 9l"),
    ("Đặt lại mật khẩu, bật MFA và cập nhật bản vá", "Đặt lại mật khẩu tài khoản bị ảnh hưởng, bật xác thực đa yếu tố cho mọi hình thức truy cập, cài bản cập nhật và bản vá.", P.recovery, IT, 48, True, "9c–9e"),
    ("Siết chặt kiểm soát biên và quy tắc truy cập", "Rà lại quy tắc tường lửa, danh sách kiểm soát truy cập ở thiết bị biên và quy tắc truy cập zero trust.", P.recovery, IT, 96, False, "9f"),
    ("Kiểm thử hệ thống trước khi đưa lại vào vận hành", "Kiểm thử kỹ, gồm đánh giá các kiểm soát an ninh; cân nhắc mô phỏng kỹ thuật tấn công để kiểm tra biện pháp phòng ngừa; xem lại thông tin đe dọa liên quan; cập nhật timeline.", P.recovery, IT, 96, True, "9g–9k"),
    ("Cập nhật tình hình cho các bên liên quan", "Cập nhật phạm vi, timeline, IOC mới, hiểu biết về tác động, tiến độ và ước tính thời gian hoàn tất ngăn chặn, loại bỏ, khôi phục. Bản gốc báo cho CISA; bước này thay bằng cập nhật nội bộ và cho đối tác.", P.communication, AN, 24, True, "8b, 11d–11e (chuyển thể)"),
    ("Chia sẻ IOC và biện pháp đối phó với đối tác tin cậy", "Chia sẻ chỉ số và biện pháp đối phó đã rút ra, sau khi lọc thông tin nhạy cảm của tổ chức.", P.communication, AN, 72, False, "4q, 11f (chuyển thể)"),
    ("Viết bản nháp báo cáo sau sự cố (postmortem)", "Rà soát từng bước của sự cố và trả lời ai, cái gì, ở đâu, tại sao, như thế nào. Commander chốt sau khi đóng vụ.", P.closure, AN, 96, True, "10a, 10f"),
    ("Bổ sung phát hiện, xử lý điểm mù log và theo dõi tiếp", "Thêm phát hiện cho các kỹ thuật đã bị khai thác, bổ sung log còn thiếu, tiếp tục theo dõi dấu hiệu hiện diện dai dẳng. Nếu chưa kịp trước khi đóng vụ, ghi thành action item của postmortem.", P.closure, IT, 120, False, "10b–10d"),
    ("Họp rút kinh nghiệm (hotwash)", "Đánh giá quy trình đã dùng, chính sách cần sửa, nhu cầu đào tạo, vai trò chưa rõ, công cụ còn thiếu và hạ tầng phòng thủ. Ghi kết quả thành action item của postmortem.", P.closure, AN, 120, False, "10i–10r"),
]


def _all_defaults():
    """Danh sách playbook mẫu; mỗi mục có source riêng và cờ auto_add (thêm vào DB đã có sẵn playbook khác)."""
    items = [dict(d, source=SOURCE, auto_add=False) for d in DEFAULTS]
    ref_steps = [
        (title, f"{desc}\n\nTham chiếu: CISA IR Checklist (Phụ lục B) mục {ref}.", phase, role, hours, required)
        for (title, desc, phase, role, hours, required, ref) in REF_STEPS
    ]
    items.append({
        "name": "Tham chiếu chuẩn: ứng phó sự cố theo CISA (điều chỉnh)",
        "incident_type": PlaybookType.other,
        "description": REF_DESCRIPTION,
        "source": REF_SOURCE,
        "steps": ref_steps,
        "auto_add": True,
    })
    return items


def seed_default_playbooks(db: Session):
    """Nạp playbook mẫu. Bảng trống thì nạp tất cả; bảng đã có dữ liệu thì chỉ thêm playbook có cờ auto_add
    nếu chưa có playbook cùng tên hoặc cùng nguồn tham chiếu (nên đổi tên playbook đó không làm hệ thống tạo lại). Đây là dữ liệu cấu hình nên không ghi vào nhật ký kiểm toán."""
    rows = db.query(Playbook).all()
    existing = {p.name.strip().lower() for p in rows}
    sources = {(p.source or "").strip() for p in rows}
    empty = not rows
    added = 0
    db.info["audit_disabled"] = True
    try:
        for item in _all_defaults():
            if item["name"].strip().lower() in existing:
                continue
            if not empty and (not item["auto_add"] or item["source"].strip() in sources):
                continue
            pb = Playbook(
                name=item["name"], incident_type=item["incident_type"],
                description=item["description"], source=item["source"], is_active=True,
            )
            db.add(pb)
            db.flush()
            for order, (title, desc, phase, role, hours, required) in enumerate(item["steps"], 1):
                db.add(PlaybookStep(
                    playbook_id=pb.id, step_order=order, title=title, description=desc,
                    phase=phase, owner_role=role, due_hours=hours, is_required=required,
                ))
            added += 1
        db.commit()
    finally:
        db.info.pop("audit_disabled", None)
    return added