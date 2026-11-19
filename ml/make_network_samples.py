import glob
import json
import os

import joblib
import numpy as np
import pandas as pd

THRESHOLD = 0.80                          # trùng threshold_network mặc định
N_ALERT, N_BENIGN, N_BELOW = 150, 140, 10 # 150 cảnh báo | 140 bình thường + 10 dưới ngưỡng = 150
CANDIDATES = 2000                         # số luồng thử mỗi nhãn, mỗi file CSV gốc
SEED = 7
OUT = "mau_demo_300"

for p in ("data/ids/processed/scaler.pkl", "data/ids/processed/feature_cols.pkl",
          "models/rf_multiclass.pkl", "models/network_labels.json"):
    if not os.path.isfile(p):
        raise SystemExit(f"Thiếu {p}. Chạy preprocess.py rồi train_multiclass.py")

scaler = joblib.load("data/ids/processed/scaler.pkl")
features = [str(c) for c in joblib.load("data/ids/processed/feature_cols.pkl")]
model = joblib.load("models/rf_multiclass.pkl")
model.set_params(verbose=0)
labels = json.load(open("models/network_labels.json", encoding="utf-8"))
classes = [labels[int(c)] for c in model.classes_]


def clean(name):  # giống train_multiclass.py
    name = str(name).replace("\ufffd", "-").replace("\u2013", "-")
    return " ".join(name.split())


frames = []
for f in sorted(glob.glob("data/ids/raw/*.csv")):
    d = pd.read_csv(f, low_memory=False)
    d.columns = d.columns.str.strip()
    for _, g in d.groupby("Label"):
        frames.append(g.sample(min(len(g), CANDIDATES), random_state=SEED))
cand = pd.concat(frames, ignore_index=True)
cand["Label"] = cand["Label"].map(clean)
cand[features] = cand[features].replace([np.inf, -np.inf], np.nan).fillna(0)

proba = model.predict_proba(scaler.transform(cand[features].to_numpy(dtype=float)))
best = proba.argmax(axis=1)
cand["pred"] = [classes[b] for b in best]
cand["conf"] = proba.max(axis=1).round(4)

# Cảnh báo "thật": dự đoán đúng nhãn tấn công và đạt ngưỡng
pool = cand[(cand["pred"] != "BENIGN") & (cand["pred"] == cand["Label"]) & (cand["conf"] >= THRESHOLD)]
groups = {l: g.sample(frac=1, random_state=SEED) for l, g in pool.groupby("pred")}

# Lấy luân phiên giữa các loại tấn công để dữ liệu đa dạng
picked, i = [], 0
while len(picked) < N_ALERT and any(len(g) > i for g in groups.values()):
    for g in groups.values():
        if i < len(g) and len(picked) < N_ALERT:
            picked.append(g.iloc[i])
    i += 1
alerts = pd.DataFrame(picked)

benign = (cand[(cand["pred"] == "BENIGN") & (cand["Label"] == "BENIGN")]
          .sample(N_BENIGN, random_state=SEED))
below = (cand[(cand["pred"] != "BENIGN") & (cand["conf"] < THRESHOLD)]
         .sample(N_BELOW, random_state=SEED))

demo = pd.concat([alerts, benign, below]).sample(frac=1, random_state=SEED).reset_index(drop=True)
out = demo[features + ["Label"]]
out.to_csv(OUT + ".csv", index=False)
out.to_json(OUT + ".json", orient="records", force_ascii=False, indent=1)

print(f"Đã tạo {OUT}.csv và {OUT}.json: {len(demo)} dòng")
print(f"Kỳ vọng với ngưỡng {THRESHOLD}: {len(alerts)} cảnh báo / {len(demo)} dòng")
print(alerts["pred"].value_counts().to_string())