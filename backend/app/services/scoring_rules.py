import json
import math
import re
from collections import Counter

# ── Tham số hợp nhất điểm (do tác giả chọn, không học từ dữ liệu; có thể chỉnh) ──
ASSET_WEIGHT = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}
UNKNOWN_ASSET_WEIGHT = 0.5
SOURCE_RELIABILITY = {
    "endpoint": 0.9, "ids_ips": 0.8, "webhook": 0.7, "manual": 0.7, "email": 0.6, "csv_upload": 0.6,
}
# Xác suất "độc hại" suy từ mức độ khai báo khi không có mô hình ML cho loại dữ liệu đó
DECLARED_PROBABILITY = {"critical": 0.90, "high": 0.75, "medium": 0.50, "low": 0.25, "info": 0.10}

W_BASE, W_ASSET, W_SOURCE = 0.5, 0.3, 0.2
URGENT_PRIORITY = 65      # điểm ưu tiên từ mức này là khẩn
URGENT_PROBABILITY = 0.80  # xác suất từ mức này trên tài sản quan trọng cũng là khẩn
AUTO_CLOSE_PROBABILITY = 0.15  # trùng ngưỡng auto_close đã đánh giá của mô hình RF
SIMILAR_MIN = 0.35
SIMILAR_TOP = 3

ZONE_LABEL = {"urgent": "Ưu tiên khẩn", "review": "Cần Analyst xem", "auto_close": "Đề xuất tự đóng"}


def asset_weight(criticality):
    return ASSET_WEIGHT.get(criticality, UNKNOWN_ASSET_WEIGHT)


def source_reliability(source):
    return SOURCE_RELIABILITY.get(source, 0.5)


def declared_probability(severity):
    return DECLARED_PROBABILITY.get(severity, 0.5)


def priority_score(p, a_weight, s_reliability):
    """Điểm ưu tiên 0 đến 100 = 100 × xác suất × (0,5 + 0,3 × tài sản + 0,2 × độ tin cậy nguồn)."""
    value = 100 * p * (W_BASE + W_ASSET * a_weight + W_SOURCE * s_reliability)
    return round(max(0.0, min(100.0, value)), 1)


def decide_zone(*, p, p_source, priority, asset_criticality, asset_w, source, declared_severity, group_has_open_risk):
    """Trả về (vùng, lý do, các luật tự đóng đã kiểm tra).

    Khẩn: điểm ưu tiên đủ cao, hoặc xác suất cao trên tài sản quan trọng.
    Tự đóng: chỉ khi đạt tất cả luật an toàn bên dưới. Còn lại: cần Analyst xem.
    """
    rules = [
        {"rule": "Xác suất do mô hình ML tính (không phải suy từ mức độ khai báo)", "passed": p_source == "rf"},
        {"rule": f"Xác suất dưới {AUTO_CLOSE_PROBABILITY}", "passed": p < AUTO_CLOSE_PROBABILITY},
        {"rule": "Tài sản đã biết và mức quan trọng thấp hoặc trung bình", "passed": asset_criticality in ("low", "medium")},
        {"rule": "Mức độ khai báo không phải cao hoặc nghiêm trọng", "passed": declared_severity not in ("high", "critical")},
        {"rule": "Không phải báo cáo thủ công của con người", "passed": source != "manual"},
        {"rule": "Nhóm cảnh báo không có alert nào đang ở vùng cần xem hoặc khẩn", "passed": not group_has_open_risk},
    ]
    if priority >= URGENT_PRIORITY:
        return "urgent", f"Điểm ưu tiên {priority} đạt ngưỡng khẩn ({URGENT_PRIORITY})", rules
    if p >= URGENT_PROBABILITY and asset_w >= ASSET_WEIGHT["high"]:
        return "urgent", f"Xác suất {p} từ {URGENT_PROBABILITY} trên tài sản mức {asset_criticality}", rules
    if all(r["passed"] for r in rules):
        return "auto_close", "Đạt mọi luật an toàn để đề xuất tự đóng", rules
    failed = [r["rule"] for r in rules if not r["passed"]]
    return "review", "Cần Analyst xem vì chưa đạt luật tự đóng: " + "; ".join(failed[:2]), rules


def extract_flow_features(raw_data):
    """Lấy đặc trưng luồng mạng từ raw_data: khóa flow_features là object, hoặc chuỗi JSON (cột CSV)."""
    if not raw_data:
        return None
    try:
        data = json.loads(raw_data)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    flow = data.get("flow_features")
    if isinstance(flow, str):
        try:
            flow = json.loads(flow)
        except ValueError:
            return None
    return flow if isinstance(flow, dict) and flow else None


# ── Cảnh báo tương tự (cosine TF-IDF trên tiêu đề, mô tả và IOC) ──
_TOKEN = re.compile(r"[\w.\-/]+", re.UNICODE)
_STOP = {"the", "a", "an", "of", "to", "in", "on", "and", "or", "is", "are", "from", "for", "with",
         "và", "của", "là", "có", "các", "một", "những", "trong", "cho", "được", "từ", "với"}


def tokens(text):
    return [t for t in (m.lower() for m in _TOKEN.findall(text or "")) if len(t) > 1 and t not in _STOP]


def rank_similar(target_text, candidates, top=SIMILAR_TOP, minimum=SIMILAR_MIN):
    """candidates: danh sách (id, văn bản). Trả về [(id, độ tương tự)] giảm dần."""
    docs = [(cid, Counter(tokens(txt))) for cid, txt in candidates]
    target = Counter(tokens(target_text))
    if not target or not docs:
        return []
    n = len(docs) + 1
    df = Counter()
    for _, c in docs:
        df.update(c.keys())
    df.update(target.keys())
    idf = {t: math.log(1 + n / df[t]) for t in df}

    def vec(c):
        return {t: f * idf.get(t, 0.0) for t, f in c.items()}

    tv = vec(target)
    tn = math.sqrt(sum(v * v for v in tv.values())) or 1.0
    out = []
    for cid, c in docs:
        dv = vec(c)
        dn = math.sqrt(sum(v * v for v in dv.values()))
        if not dn:
            continue
        dot = sum(v * dv.get(t, 0.0) for t, v in tv.items())
        sim = dot / (tn * dn)
        if sim >= minimum:
            out.append((cid, round(sim, 3)))
    out.sort(key=lambda x: -x[1])
    return out[:top]
