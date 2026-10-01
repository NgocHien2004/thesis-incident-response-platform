import numpy as np
import joblib
import os
import json
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report, confusion_matrix,
    precision_recall_curve, auc, roc_auc_score
)
import matplotlib
matplotlib.use('Agg')  # không cần GUI
import matplotlib.pyplot as plt

DATA_DIR   = "data/processed"
MODEL_DIR  = "models"
os.makedirs(MODEL_DIR, exist_ok=True)

# ── Load data ──
print("Loading data...")
X_train = np.load(os.path.join(DATA_DIR, "X_train.npy"))
X_test  = np.load(os.path.join(DATA_DIR, "X_test.npy"))
y_train = np.load(os.path.join(DATA_DIR, "y_train_binary.npy"))
y_test  = np.load(os.path.join(DATA_DIR, "y_test_binary.npy"))
le      = joblib.load(os.path.join(DATA_DIR, "label_encoder.pkl"))
feature_cols = joblib.load(os.path.join(DATA_DIR, "feature_cols.pkl"))

print(f"Train: {X_train.shape} | Test: {X_test.shape}")
print(f"Attack ratio train: {y_train.mean():.2%}")

# ── Train Random Forest ──
print("\nTraining Random Forest...")
rf = RandomForestClassifier(
    n_estimators=100,
    max_depth=20,
    class_weight="balanced",   # xử lý imbalanced
    random_state=42,
    n_jobs=-1,                 # dùng tất cả CPU
    verbose=1
)
rf.fit(X_train, y_train)
print("Done!")

# ── Evaluate ──
print("\nEvaluating...")
y_pred      = rf.predict(X_test)
y_pred_prob = rf.predict_proba(X_test)[:, 1]

print("\n── Classification Report ──")
print(classification_report(y_test, y_pred, target_names=["BENIGN", "ATTACK"]))

# PR-AUC
precision, recall, thresholds = precision_recall_curve(y_test, y_pred_prob)
pr_auc = auc(recall, precision)
print(f"PR-AUC: {pr_auc:.4f}")

# ROC-AUC
roc_auc = roc_auc_score(y_test, y_pred_prob)
print(f"ROC-AUC: {roc_auc:.4f}")

# Confusion matrix
cm = confusion_matrix(y_test, y_pred)
print(f"\nConfusion Matrix:")
print(f"  TN={cm[0,0]:,} FP={cm[0,1]:,}")
print(f"  FN={cm[1,0]:,} TP={cm[1,1]:,}")

# ── Ngưỡng 3 vùng ──
print("\n── Phân tích ngưỡng 3 vùng ──")
thresholds_3 = {
    "auto_close":  0.15,   # dưới ngưỡng → tự đóng (benign chắc chắn)
    "review":      0.50,   # trung gian → analyst xem
    "urgent":      0.80,   # trên ngưỡng → ưu tiên khẩn
}
for name, t in thresholds_3.items():
    count = (y_pred_prob >= t).sum() if name != "auto_close" else (y_pred_prob < t).sum()
    pct   = count / len(y_pred_prob) * 100
    print(f"  {name} (t={t}): {count:,} alerts ({pct:.1f}%)")

# ── Feature importance ──
print("\n── Top 20 Feature Importance ──")
importances = rf.feature_importances_
indices     = np.argsort(importances)[::-1][:20]
for i, idx in enumerate(indices):
    print(f"  {i+1:2d}. {feature_cols[idx]:<40} {importances[idx]:.4f}")

# ── Save model ──
print("\nSaving model...")
joblib.dump(rf, os.path.join(MODEL_DIR, "rf_binary.pkl"))

# Save metrics
metrics = {
    "pr_auc":  round(pr_auc, 4),
    "roc_auc": round(roc_auc, 4),
    "confusion_matrix": cm.tolist(),
    "thresholds": thresholds_3,
    "top_features": [feature_cols[i] for i in indices],
}
with open(os.path.join(MODEL_DIR, "metrics.json"), "w") as f:
    json.dump(metrics, f, indent=2)

# ── Plot PR curve ──
plt.figure(figsize=(8, 6))
plt.plot(recall, precision, color='blue', lw=2, label=f'PR curve (AUC = {pr_auc:.4f})')
plt.xlabel('Recall')
plt.ylabel('Precision')
plt.title('Precision-Recall Curve — Random Forest Binary Classification')
plt.legend()
plt.grid(True)
plt.savefig(os.path.join(MODEL_DIR, "pr_curve.png"), dpi=150, bbox_inches='tight')
print("PR curve saved!")

# ── Plot Confusion Matrix ──
plt.figure(figsize=(6, 5))
plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
plt.colorbar()
plt.xticks([0,1], ["BENIGN", "ATTACK"])
plt.yticks([0,1], ["BENIGN", "ATTACK"])
plt.xlabel('Predicted')
plt.ylabel('Actual')
plt.title('Confusion Matrix')
for i in range(2):
    for j in range(2):
        plt.text(j, i, f'{cm[i,j]:,}', ha='center', va='center',
                 color='white' if cm[i,j] > cm.max()/2 else 'black')
plt.savefig(os.path.join(MODEL_DIR, "confusion_matrix.png"), dpi=150, bbox_inches='tight')
print("Confusion matrix saved!")

print("\n✓ Xong! Model lưu tại models/rf_binary.pkl")