# Thư mục ml

## Bố cục dữ liệu
```
data/
  ids/raw/         CSV gốc CIC-IDS2017 (tự tải, 8 file MachineLearningCVE)
  ids/processed/   do preprocess.py tạo
  email/kaggle/    6 file CSV nguồn email: ceas_08, enron, ling, spamassasin, nazario, nigerian_fraud
models/            mô hình đã huấn luyện (không kèm trong gói)
results/           báo cáo đánh giá (multiclass_report.json, email_eval.json)
```

## Thứ tự chạy
1. `python preprocess.py` (cần CSV trong `data/ids/raw`; xóa `data/ids/processed` cũ trước khi chạy lại)
2. `python train_multiclass.py` (15 nhãn; thêm `--sample 0.1 --trees 30` để chạy thử nhanh)
3. `python train_email.py` (đọc `data/email/kaggle`; thêm `--skip-eval` để chỉ huấn luyện, bỏ bước đánh giá)
4. `uvicorn serve:app --port 8001` (khởi động lại sau mỗi lần huấn luyện)
5. `python make_network_samples.py` (tùy chọn: tạo file mẫu để thử upload; chạy lại sau mỗi lần huấn luyện)

## Ghi chú
- `preprocess.py` loại dòng trùng trước khi chia train/test và chỉ fit scaler trên tập train.
- `serve.py` dừng nếu thiếu `rf_multiclass.pkl`, `network_labels.json`, `scaler.pkl` hoặc `feature_cols.pkl`. Thiếu `email_svm.pkl` thì nguồn email trả 503.
- Phiên bản mô hình là 8 ký tự đầu SHA-256 của file `.pkl`, nên huấn luyện lại thì phiên bản đổi.
- Quy tắc sinh cảnh báo luồng mạng đang dùng: nhãn dự đoán khác BENIGN và confidence (xác suất của nhãn đó) lớn hơn hoặc bằng ngưỡng. Phép so với quy tắc dùng `1 − P(BENIGN)` nằm ở `SYSTEM_DESIGN.md` mục 8.1.