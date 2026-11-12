import json
import os
from sqlalchemy import insert
from database import SessionLocal
from app.models.upload import Upload
from app.models.alert import Alert
from app.models.ml_model import MLModel, Label
from app.core.constants import FILE_FORMATS
from app.core.timeutils import utcnow
from app.services import classifier
from app.services.classifier import AIError
from app.services.parsing import Schema, ValidationError, iter_rows
from app.services.settings_store import get_float, get_int

INSERT_CHUNK = 1000

def _fail(upload_id: int, message: str):
    # Phiên riêng: dù phiên chính đã hỏng, vẫn ghi được trạng thái lỗi
    with SessionLocal() as db:
        up = db.get(Upload, upload_id)
        if up:
            up.status = "failed"
            up.error_message = message[:2000]
            up.processed_at = utcnow()
            db.commit()

def process_upload(upload_id: int):
    try:
        _process(upload_id)
    except (AIError, ValidationError) as e:
        _fail(upload_id, str(e))
    except Exception as e:
        _fail(upload_id, f"Lỗi không mong đợi khi xử lý: {e.__class__.__name__}: {e}")

def _process(upload_id: int):
    with SessionLocal() as db:
        up = db.get(Upload, upload_id)
        if not up or up.status not in ("pending",):
            return
        data_type = up.data_type
        fmt = FILE_FORMATS[os.path.splitext(up.original_filename)[1].lower()]
        up.status = "processing"
        up.error_message = None
        db.commit()

        threshold = get_float(db, f"threshold_{data_type}")
        batch_size = get_int(db, "batch_size")
        # Chụp lại cấu hình tại thời điểm xử lý
        dangerous = {l.code for l in db.query(Label).filter(
            Label.data_type == data_type, Label.is_dangerous == True, Label.is_active == True)}  # noqa: E712
        known = {l.code for l in db.query(Label).filter(Label.data_type == data_type)}

        model = classifier.get_active_model(db, data_type)
        features = json.loads(model.feature_names) if model.feature_names else None
        schema = Schema(data_type, features)
        up.model_id, up.threshold_used = model.id, threshold
        db.commit()

        version_seen = None
        counts, conf_sum, total = {}, 0.0, 0
        pending_alerts, new_labels = [], {}
        batch = []

        def flush():
            nonlocal version_seen, conf_sum, total
            if not batch:
                return
            data = classifier.predict_batch(data_type, [r for _, r in batch])
            version = data.get("model_version")
            if version_seen is None:
                version_seen = version
            elif version != version_seen:
                raise AIError(f"Phiên bản mô hình đổi giữa chừng ({version_seen} sang {version}); hãy upload lại")
            for (idx, row), res in zip(batch, data["results"]):
                label, conf = str(res["label"]), float(res["confidence"])
                if label not in known and label not in new_labels:
                    new_labels[label] = classifier.default_dangerous(label)
                    if new_labels[label]:
                        dangerous.add(label)
                counts[label] = counts.get(label, 0) + 1
                conf_sum += conf
                total += 1
                if label in dangerous and conf >= threshold:
                    pending_alerts.append((idx, label, conf, row))
            up.processed_rows = total
            db.commit()
            batch.clear()

        for idx, row in iter_rows(up.stored_path, fmt, schema):
            batch.append((idx, row))
            if len(batch) >= batch_size:
                flush()
        flush()

        if total != up.row_count:
            raise ValidationError(f"Số dòng xử lý ({total}) khác số dòng đã kiểm tra ({up.row_count}); file có thể đã bị đổi")

        # Từ đây một giao dịch duy nhất: có lỗi thì không cảnh báo nào được ghi
        now = utcnow()
        try:
            for code, is_danger in new_labels.items():
                db.add(Label(data_type=data_type, code=code, name_vi=code, is_dangerous=is_danger, is_active=True))
            if version_seen and version_seen != model.version:
                m = db.query(MLModel).filter(MLModel.task_type == data_type, MLModel.version == version_seen).first()
                if m:
                    up.model_id = m.id
            rows = []
            for idx, label, conf, row in pending_alerts:
                rows.append({
                    "incident_id": up.incident_id, "upload_id": up.id, "row_index": idx,
                    "predicted_label": label, "confidence": conf, "source_type": data_type,
                    "row_data": json.dumps(row, ensure_ascii=False),
                    "auto_linked": True, "linked_at": now, "verification_status": "unverified",
                    "created_at": now,
                })
            for i in range(0, len(rows), INSERT_CHUNK):
                db.execute(insert(Alert), rows[i:i + INSERT_CHUNK])
            up.dangerous_labels_used = json.dumps(sorted(dangerous), ensure_ascii=False)
            up.label_distribution = json.dumps(counts, ensure_ascii=False)
            up.avg_confidence = round(conf_sum / total, 6) if total else None
            up.alert_count = len(rows)
            up.status = "completed"
            up.processed_at = now
            db.commit()
        except Exception:
            db.rollback()
            raise
