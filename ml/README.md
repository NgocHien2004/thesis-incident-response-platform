# Thư mục ml

## Bố cục dữ liệu
```
data/
  ids/raw/         CSV gốc CIC-IDS2017 (tự tải)
  ids/processed/   do preprocess.py tạo
  email/           spamassassin.jsonl (đã kèm; tạo lại bằng export_spamassassin.js)
models/            mô hình đã huấn luyện (không kèm trong gói)
results/           báo cáo đánh giá
```

## Thứ tự chạy
1. `python preprocess.py` (cần CSV trong `data/ids/raw`)
2. `python train.py` (mô hình nhị phân, tạo `models/rf_binary.pkl`, bắt buộc để `serve.py` chạy)
3. `python train_baselines.py` (so sánh các mô hình, ghi `results/baseline_comparison.json`)
4. `python train_multiclass.py` (15 nhãn; thêm `--sample 0.1 --trees 30` để chạy thử nhanh)
5. `python train_email.py` (đọc `data/email/spamassassin.jsonl`)
6. `uvicorn serve:app --port 8001`

## Ghi chú
- ATT&CK (`attck_*.py`, `download_attck.py`) không còn dùng trong bản v2; `serve.py` bỏ qua nếu thiếu chỉ mục.
- `data/attck_enterprise.json` không kèm trong gói (tải lại bằng `python download_attck.py`).
