import os
import sys
import json
import random
import itertools
import importlib
import glob
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.abspath(os.path.join(HERE, "..", "backend"))
if not os.path.isdir(os.path.join(BACKEND, "app")):
    BACKEND = os.path.abspath(os.path.join(HERE, "..", "..", "backend"))
sys.path.insert(0, BACKEND)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base

for f in glob.glob(os.path.join(BACKEND, "app", "models", "*.py")):
    name = os.path.basename(f)[:-3]
    if name != "__init__":
        importlib.import_module("app.models." + name)

from app.models.alert import Alert, AlertSource
import app.services.dedup as dedup

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
db = sessionmaker(bind=engine)()

BASE = datetime(2026, 10, 1, 8, 0, 0)


class FakeDT(datetime):
    current = BASE

    @classmethod
    def now(cls, tz=None):
        return cls.current.replace(tzinfo=tz)


dedup.datetime = FakeDT

random.seed(42)
events = []
inc_type = {}
_inc = itertools.count(1)
_asset = itertools.count(1)
_ip = itertools.count(1)


def ip():
    n = next(_ip)
    return f"203.0.{n // 250}.{n % 250 + 1}"


def new_incident(kind):
    i = next(_inc)
    inc_type[i] = kind
    return i


def add(t, inc, ioc, asset, title="Cảnh báo"):
    events.append({"t": t, "inc": inc, "ioc": ioc, "asset": asset, "title": title})


def variants(s):
    return random.choice([s, s.upper(), " " + s + " ", s.title()])


t0 = 0
for _ in range(6):                                  # A: gom đơn giản, cùng IOC + cùng tài sản
    i, a, x = new_incident("A_cung_ioc_tai_san"), next(_asset), ip()
    for k in range(random.randint(3, 6)):
        add(t0 + k * random.randint(3, 9), i, variants(x), a)
    t0 += 20
for _ in range(2):                                  # B: nhiều IOC, khác thứ tự/chữ hoa
    i, a, x, d = new_incident("B_khac_dinh_dang_ioc"), next(_asset), ip(), f"evil{next(_ip)}.example.com"
    add(t0, i, f"{x}, {d}", a)
    add(t0 + 5, i, f"{d.upper()},{x}", a)
    add(t0 + 9, i, f" {x} ,{d} ", a)
    t0 += 20
for _ in range(3):                                  # C: lây lan sang nhiều tài sản
    i, x = new_incident("C_lay_lan_nhieu_tai_san"), ip()
    a1, a2, a3 = next(_asset), next(_asset), next(_asset)
    add(t0, i, x, a1); add(t0 + 6, i, x, a1)
    add(t0 + 12, i, x, a2); add(t0 + 18, i, x, a3)
    t0 += 30
for _ in range(2):                                  # D: một số cảnh báo thiếu IOC
    i, a, x = new_incident("D_thieu_ioc"), next(_asset), ip()
    add(t0, i, x, a); add(t0 + 4, i, x, a)
    add(t0 + 8, i, None, a); add(t0 + 12, i, None, a)
    t0 += 25
for _ in range(2):                                  # E1: nhịp chậm nhưng liên tục (<60 phút giữa 2 alert)
    i, a, x = new_incident("E1_cham_lien_tuc"), next(_asset), ip()
    for k in range(4):
        add(t0 + k * 45, i, x, a)
    t0 += 200
for _ in range(2):                                  # E2: ngắt quãng > 60 phút giữa 2 nửa
    i, a, x = new_incident("E2_ngat_quang_90p"), next(_asset), ip()
    add(t0, i, x, a); add(t0 + 10, i, x, a)
    add(t0 + 100, i, x, a); add(t0 + 110, i, x, a)
    t0 += 220
for _ in range(2):                                  # F: IOC chồng lấn một phần
    i, a = new_incident("F_ioc_chong_lan"), next(_asset)
    p, q = ip(), ip()
    add(t0, i, f"{p},{q}", a); add(t0 + 5, i, q, a); add(t0 + 10, i, p, a)
    t0 += 25
for _ in range(2):                                  # G: hai sự cố khác nhau dùng chung IOC + tài sản
    a, x = next(_asset), ip()
    i1, i2 = new_incident("G_va_cham_ioc_tai_san"), new_incident("G_va_cham_ioc_tai_san")
    add(t0, i1, x, a); add(t0 + 5, i1, x, a)
    add(t0 + 20, i2, x, a); add(t0 + 25, i2, x, a)
    t0 += 45
for _ in range(2):                                  # I: có IOC nhưng không gắn tài sản
    i, x = new_incident("I_khong_co_tai_san"), ip()
    add(t0, i, x, None); add(t0 + 6, i, x, None); add(t0 + 12, i, x, None)
    t0 += 25
for _ in range(14):                                 # H: nhiễu, mỗi cảnh báo là một sự cố riêng
    i = new_incident("H_don_le")
    add(t0, i, ip(), random.choice([None, next(_asset)]))
    t0 += random.randint(2, 6)

events.sort(key=lambda e: e["t"])
group_of, true_of = {}, {}
for n, e in enumerate(events):
    FakeDT.current = BASE + timedelta(minutes=e["t"])
    a = Alert(title=e["title"], source=AlertSource.ids_ips, ioc=e["ioc"], affected_asset=e["asset"])
    db.add(a)
    db.commit()
    db.refresh(a)
    dedup.process_alert(a, db)
    group_of[n], true_of[n] = a.group_id, e["inc"]

N = len(events)
tp = fp = fn = 0
fn_by, fp_pairs = {}, []
for i, j in itertools.combinations(range(N), 2):
    same_true, same_grp = true_of[i] == true_of[j], group_of[i] == group_of[j]
    if same_true and same_grp:
        tp += 1
    elif same_grp and not same_true:
        fp += 1
        fp_pairs.append((inc_type[true_of[i]], inc_type[true_of[j]]))
    elif same_true and not same_grp:
        fn += 1
        fn_by[inc_type[true_of[i]]] = fn_by.get(inc_type[true_of[i]], 0) + 1

P = tp / (tp + fp) if tp + fp else 0.0
R = tp / (tp + fn) if tp + fn else 0.0
F1 = 2 * P * R / (P + R) if P + R else 0.0

multi = [k for k in set(true_of.values()) if sum(1 for v in true_of.values() if v == k) >= 2]
complete = sum(1 for k in multi if len({group_of[n] for n in range(N) if true_of[n] == k}) == 1)

by_type = {}
for k in sorted(set(inc_type[i] for i in multi)):
    ids = [i for i in multi if inc_type[i] == k]
    pairs = [(a, b) for a, b in itertools.combinations(range(N), 2)
             if true_of[a] == true_of[b] and true_of[a] in ids]
    ok = sum(1 for a, b in pairs if group_of[a] == group_of[b])
    done = sum(1 for i in ids if len({group_of[n] for n in range(N) if true_of[n] == i}) == 1)
    by_type[k] = {"incidents": len(ids), "pairs": len(pairs), "pair_recall_pct": round(100 * ok / len(pairs), 1),
                  "incidents_fully_grouped": f"{done}/{len(ids)}"}

print(f"Tập đánh giá mô phỏng: {N} cảnh báo, {len(set(true_of.values()))} sự cố thật "
      f"({len(multi)} sự cố có ≥2 cảnh báo), {len(set(group_of.values()))} nhóm do hệ thống tạo ra\n")
print(f"Theo cặp cảnh báo:  Precision = {100*P:.1f}%   Recall = {100*R:.1f}%   F1 = {100*F1:.1f}%")
print(f"                    (TP={tp}, FP={fp}, FN={fn})")
print(f"Sự cố được gom trọn vẹn vào đúng 1 nhóm: {complete}/{len(multi)} = {100*complete/len(multi):.1f}%\n")
print("Chi tiết theo tình huống:")
for k, v in by_type.items():
    print(f"  {k:26} sự cố={v['incidents']:>2}  recall theo cặp={v['pair_recall_pct']:>5}%  gom trọn vẹn={v['incidents_fully_grouped']}")
if fp_pairs:
    kinds = {}
    for a, b in fp_pairs:
        kinds[(a, b)] = kinds.get((a, b), 0) + 1
    print("\nCặp bị gom nhầm (FP): " + "; ".join(f"{a}↔{b} ×{n}" for (a, b), n in kinds.items()))

print("\nLưu ý: tỷ lệ các tình huống do tác giả chọn nên số tổng hợp phụ thuộc vào cách trộn đó; "
      "giá trị chính của bài đánh giá là chỉ ra tình huống nào luật gom nhóm xử lý được hay không.")

out = os.path.join(HERE, "results", "grouping_eval_results.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump({"alerts": N, "true_incidents": len(set(true_of.values())), "groups": len(set(group_of.values())),
           "pair_precision_pct": round(100 * P, 1), "pair_recall_pct": round(100 * R, 1), "pair_f1_pct": round(100 * F1, 1),
           "tp": tp, "fp": fp, "fn": fn, "incidents_fully_grouped": f"{complete}/{len(multi)}",
           "by_scenario": by_type}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"Đã ghi {out}")