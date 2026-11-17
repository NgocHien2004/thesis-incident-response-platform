import json
import os

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "models_fake")
rng = np.random.default_rng(0)

feature_path = os.path.join(HERE, "data", "ids", "processed", "feature_cols.pkl")
labels_path = os.path.join(HERE, "models", "network_labels.json")
for p in (feature_path, labels_path):
    if not os.path.isfile(p):
        raise SystemExit(f"Thiếu {os.path.relpath(p, HERE)}. Chạy preprocess.py và train_multiclass.py trước")

features = [str(c) for c in joblib.load(feature_path)]
labels = json.load(open(labels_path, encoding="utf-8"))
os.makedirs(OUT, exist_ok=True)

# ---- mạng: luật giả trên hai đặc trưng (đã chuẩn hóa), chỉ để thử luồng, không có ý nghĩa an ninh ----
def col(name, default):
    low = {f.strip().casefold(): i for i, f in enumerate(features)}
    return low.get(name.casefold(), default)

i_dur, i_pkt = col("Flow Duration", 0), col("Total Fwd Packets", 1)
benign, ddos, scan = labels.index("BENIGN"), labels.index("DDoS"), labels.index("PortScan")
X = rng.normal(size=(6000, len(features)))
y = np.full(len(X), benign)
y[X[:, i_dur] > 1.0] = ddos
y[(X[:, i_dur] <= 1.0) & (X[:, i_pkt] < -1.0)] = scan
net = RandomForestClassifier(n_estimators=20, max_depth=4, max_features=None, random_state=0, n_jobs=-1).fit(X, y)
joblib.dump(net, os.path.join(OUT, "fake_network.pkl"))
with open(os.path.join(OUT, "network_labels.json"), "w", encoding="utf-8") as f:
    json.dump(labels, f, ensure_ascii=False, indent=1)

# ---- email: từ khóa giả ----
spam_words = "free money winner prize verify account password click urgent bank offer cash claim".split()
ham_words = "meeting schedule report lunch project thanks team agenda review notes tomorrow".split()
texts, tags = [], []
for _ in range(400):
    is_spam = int(rng.random() < 0.5)
    pool = spam_words if is_spam else ham_words
    other = ham_words if is_spam else spam_words
    words = list(rng.choice(pool, 6)) + list(rng.choice(other, 1))
    rng.shuffle(words)
    texts.append(" ".join(words))
    tags.append(is_spam)
mail = make_pipeline(TfidfVectorizer(), LogisticRegression(C=10)).fit(texts, tags)
joblib.dump(mail, os.path.join(OUT, "fake_email.pkl"))

# ---- tên hiển thị, tiền tố phiên bản, tên file mà serve.py đọc ----
info = {"network": {"name": "Fake network model", "prefix": "fake_network", "file": "fake_network.pkl"},
        "email": {"name": "Fake email model", "prefix": "fake_email", "file": "fake_email.pkl"}}
with open(os.path.join(OUT, "model_info.json"), "w", encoding="utf-8") as f:
    json.dump(info, f, ensure_ascii=False, indent=1)

print(f"Đã tạo mô hình giả trong {os.path.relpath(OUT, HERE)}/")
print("Chạy dịch vụ AI với bộ này (PowerShell):")
print('  $env:MODEL_DIR="models_fake"; uvicorn serve:app --port 8001')
print("Quay về mô hình thật: tắt dịch vụ, mở lại cửa sổ mới (hoặc Remove-Item Env:MODEL_DIR) rồi chạy lại; sau mỗi lần đổi bấm Đồng bộ từ dịch vụ AI.")
print("Luật giả: Flow Duration chuẩn hóa > 1 thành DDoS; còn lại Total Fwd Packets < -1 thành PortScan; email có từ khóa như free, money, verify thành SPAM.")