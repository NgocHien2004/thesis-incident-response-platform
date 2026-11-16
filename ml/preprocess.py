import os

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data", "ids", "raw")
OUTPUT_DIR = os.path.join(HERE, "data", "ids", "processed")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Bước 1: Đọc và gộp tất cả file ──
print("Đang đọc data...")
dfs = []
for f in sorted(os.listdir(DATA_DIR)):
    if f.endswith(".csv"):
        part = pd.read_csv(os.path.join(DATA_DIR, f), low_memory=False)
        part.columns = part.columns.str.strip()  # bỏ khoảng trắng tên cột; cột trùng tên thành ".1"
        dfs.append(part)
        print(f"  {f}: {len(part):,} dòng")

df = pd.concat(dfs, ignore_index=True)
del dfs
print(f"\nTổng: {len(df):,} dòng, {len(df.columns)} cột")

# ── Bước 2: Làm sạch ──
print("\nLàm sạch data...")
drop_cols = ["Flow ID", "Source IP", "Destination IP", "Timestamp"]
df.drop(columns=[c for c in drop_cols if c in df.columns], inplace=True)

df.replace([np.inf, -np.inf], np.nan, inplace=True)
print(f"  Số giá trị null/inf: {int(df.isnull().sum().sum()):,}")
df.dropna(inplace=True)
print(f"  Còn lại sau dropna: {len(df):,} dòng")

# ── Bước 3: Loại dòng trùng trước khi chia, để dòng test không giống hệt dòng train ──
feature_cols = [c for c in df.columns if c != "Label"]
before = df["Label"].value_counts()
n_before = len(df)
df = df.drop_duplicates().reset_index(drop=True)
after = df["Label"].value_counts()
print(f"\nLoại dòng trùng (giống hệt ở mọi cột kể cả nhãn): {n_before:,} -> {len(df):,} "
      f"(bỏ {n_before - len(df):,} dòng, {100 * (n_before - len(df)) / n_before:.1f}%)")
print(f"{'Lớp':<32}{'Trước':>11}{'Sau':>11}{'Bỏ (%)':>9}")
for label in before.index:
    b, a = int(before[label]), int(after.get(label, 0))
    print(f"{str(label):<32}{b:>11,}{a:>11,}{100 * (b - a) / b:>8.1f}%")
conflict = int(df.duplicated(subset=feature_cols, keep=False).sum())
print(f"Dòng có đặc trưng giống dòng khác nhưng nhãn khác (nhãn nhiễu, được giữ nguyên): {conflict:,}")

# ── Bước 4: Nhãn ──
le = LabelEncoder()
y = le.fit_transform(df["Label"])
print(f"\nMulti-class: {len(le.classes_)} loại: {list(le.classes_)}")
joblib.dump(le, os.path.join(OUTPUT_DIR, "label_encoder.pkl"))
is_attack = (df["Label"] != "BENIGN").to_numpy()
X = df[feature_cols].to_numpy(dtype=np.float64)
del df

# ── Bước 5: Chia train/test (80/20) ──
print("\nChia train/test (80/20)...")
idx = np.arange(len(y))
try:
    tr, te = train_test_split(idx, test_size=0.2, random_state=42, stratify=y)
except ValueError:
    print("  Có lớp quá ít mẫu để chia theo từng lớp, chia theo BENIGN/tấn công")
    tr, te = train_test_split(idx, test_size=0.2, random_state=42, stratify=is_attack)
X_train, X_test, y_train, y_test = X[tr], X[te], y[tr], y[te]
del X
print(f"  Train: {len(tr):,} | Test: {len(te):,}")

# ── Bước 6: Scale, chỉ học trên tập train ──
print("Scaling features (fit trên tập train)...")
scaler = StandardScaler().fit(X_train)
X_train = scaler.transform(X_train).astype(np.float32)
X_test = scaler.transform(X_test).astype(np.float32)
joblib.dump(scaler, os.path.join(OUTPUT_DIR, "scaler.pkl"))
joblib.dump(feature_cols, os.path.join(OUTPUT_DIR, "feature_cols.pkl"))

print(f"\n{'Lớp':<32}{'Train':>11}{'Test':>9}")
for i, name in enumerate(le.classes_):
    print(f"{str(name):<32}{int((y_train == i).sum()):>11,}{int((y_test == i).sum()):>9,}")

# ── Bước 7: Lưu ──
print("\nLưu data...")
np.save(os.path.join(OUTPUT_DIR, "X_train.npy"), X_train)
np.save(os.path.join(OUTPUT_DIR, "X_test.npy"), X_test)
np.save(os.path.join(OUTPUT_DIR, "y_train_multi.npy"), y_train)
np.save(os.path.join(OUTPUT_DIR, "y_test_multi.npy"), y_test)

print("\nXong! Files trong data/ids/processed/:")
for f in sorted(os.listdir(OUTPUT_DIR)):
    size = os.path.getsize(os.path.join(OUTPUT_DIR, f)) / 1024 / 1024
    print(f"  {f}: {size:.1f} MB")