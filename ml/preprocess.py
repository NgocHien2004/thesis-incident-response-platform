import pandas as pd
import numpy as np
import os
import joblib
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split

DATA_DIR    = "data/raw"
OUTPUT_DIR  = "data/processed"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Bước 1: Đọc và gộp tất cả file ──
print("Đang đọc data...")
dfs = []
for f in os.listdir(DATA_DIR):
    if f.endswith(".csv"):
        df = pd.read_csv(os.path.join(DATA_DIR, f), low_memory=False)
        df.columns = df.columns.str.strip()  # bỏ khoảng trắng tên cột
        dfs.append(df)
        print(f"  {f}: {len(df):,} dòng")

df = pd.concat(dfs, ignore_index=True)
print(f"\nTổng: {len(df):,} dòng, {len(df.columns)} cột")

# ── Bước 2: Làm sạch ──
print("\nLàm sạch data...")

# Bỏ cột không cần
drop_cols = ["Flow ID", "Source IP", "Destination IP", "Timestamp"]
df.drop(columns=[c for c in drop_cols if c in df.columns], inplace=True)

# Xử lý giá trị vô cực và NaN
df.replace([np.inf, -np.inf], np.nan, inplace=True)
null_count = df.isnull().sum().sum()
print(f"  Số giá trị null/inf: {null_count:,}")
df.dropna(inplace=True)
print(f"  Còn lại sau dropna: {len(df):,} dòng")

# ── Bước 3: Nhãn ──
print("\nPhân phối nhãn gốc:")
print(df["Label"].value_counts())

# Binary: BENIGN=0, tất cả attack=1
df["label_binary"] = (df["Label"] != "BENIGN").astype(int)
print(f"\nBinary — BENIGN: {(df['label_binary']==0).sum():,} | ATTACK: {(df['label_binary']==1).sum():,}")

# Multi-class
le = LabelEncoder()
df["label_multi"] = le.fit_transform(df["Label"])
print(f"Multi-class — {len(le.classes_)} loại: {list(le.classes_)}")
joblib.dump(le, os.path.join(OUTPUT_DIR, "label_encoder.pkl"))

# ── Bước 4: Features ──
feature_cols = [c for c in df.columns if c not in ["Label", "label_binary", "label_multi"]]
X = df[feature_cols]
y_binary = df["label_binary"]
y_multi  = df["label_multi"]

# ── Bước 5: Scale ──
print("\nScaling features...")
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
joblib.dump(scaler, os.path.join(OUTPUT_DIR, "scaler.pkl"))
joblib.dump(feature_cols, os.path.join(OUTPUT_DIR, "feature_cols.pkl"))

# ── Bước 6: Train/test split ──
print("Chia train/test (80/20)...")
X_train, X_test, y_train_b, y_test_b, y_train_m, y_test_m = train_test_split(
    X_scaled, y_binary, y_multi,
    test_size=0.2,
    random_state=42,
    stratify=y_binary
)

print(f"  Train: {len(X_train):,} | Test: {len(X_test):,}")

# ── Bước 7: Lưu ──
print("\nLưu data...")
np.save(os.path.join(OUTPUT_DIR, "X_train.npy"), X_train)
np.save(os.path.join(OUTPUT_DIR, "X_test.npy"),  X_test)
np.save(os.path.join(OUTPUT_DIR, "y_train_binary.npy"), y_train_b.values)
np.save(os.path.join(OUTPUT_DIR, "y_test_binary.npy"),  y_test_b.values)
np.save(os.path.join(OUTPUT_DIR, "y_train_multi.npy"),  y_train_m.values)
np.save(os.path.join(OUTPUT_DIR, "y_test_multi.npy"),   y_test_m.values)

print("\nXong! Files trong data/processed/:")
for f in os.listdir(OUTPUT_DIR):
    size = os.path.getsize(os.path.join(OUTPUT_DIR, f)) / 1024 / 1024
    print(f"  {f}: {size:.1f} MB")