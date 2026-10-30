import os
import sys
import json
import argparse
import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--ai", default="http://127.0.0.1:8001")
ap.add_argument("--set", default=os.path.join(HERE, "attck_eval_set.json"))
ap.add_argument("--data", default=os.path.join(HERE, "..", "ml", "data", "attck_enterprise.json"))
ap.add_argument("--out", default=os.path.join(HERE, "attck_eval_results.json"))
args = ap.parse_args()

items = json.load(open(args.set, encoding="utf-8"))["items"]

known = {}
if os.path.exists(args.data):
    for o in json.load(open(args.data, encoding="utf-8"))["objects"]:
        if o.get("type") == "attack-pattern" and not o.get("revoked") and not o.get("x_mitre_deprecated"):
            for r in o.get("external_references", []):
                if r.get("source_name") == "mitre-attack":
                    known[r["external_id"]] = o["name"]
    bad = [(i["id"], t) for i in items for t in i["expected"] if t not in known]
    if bad:
        print("CẢNH BÁO: nhãn không có trong dữ liệu ATT&CK đang dùng:", bad)
        print("Các câu này sẽ luôn bị tính là trượt; hãy sửa nhãn trước khi dùng kết quả.\n")
else:
    print(f"Không tìm thấy {args.data}; bỏ qua kiểm tra nhãn.\n")

parent = lambda t: t.split(".")[0]
client = httpx.Client(timeout=30.0)

try:
    client.get(args.ai + "/").raise_for_status()
except Exception as e:
    print(f"Không kết nối được AI service tại {args.ai}: {e}")
    sys.exit(1)

rows = []
for it in items:
    for lang in ("en", "vi"):
        r = client.post(args.ai + "/attck/search", json={"description": it[lang], "top_k": 10})
        r.raise_for_status()
        res = r.json()["results"]
        ranked = [x["id"] for x in res]
        exp = set(it["expected"])
        exp_parent = {parent(t) for t in exp}

        def first_rank(match):
            for k, tid in enumerate(ranked, 1):
                if match(tid):
                    return k
            return None

        rows.append({
            "id": it["id"], "category": it["category"], "lang": lang, "query": it[lang],
            "expected": it["expected"],
            "rank_strict": first_rank(lambda t: t in exp),
            "rank_parent": first_rank(lambda t: parent(t) in exp_parent),
            "top5": [f"{x['id']} {x['name']}" for x in res[:5]],
        })


def summarize(sel):
    n = len(sel)
    out = {"n": n}
    for key, label in (("rank_strict", "strict"), ("rank_parent", "parent")):
        for k in (1, 3, 5):
            out[f"top{k}_{label}"] = round(100 * sum(1 for r in sel if r[key] and r[key] <= k) / n, 1)
    out["mrr_strict"] = round(sum(1 / r["rank_strict"] for r in sel if r["rank_strict"]) / n, 3)
    return out


summary = {"all": {}, "by_category": {}}
for lang in ("en", "vi"):
    sel = [r for r in rows if r["lang"] == lang]
    summary["all"][lang] = summarize(sel)
    for c in sorted({r["category"] for r in sel}):
        summary["by_category"].setdefault(c, {})[lang] = summarize([r for r in sel if r["category"] == c])
summary["random_baseline_top5_pct"] = round(100 * 5 / max(len(known), 697), 2)

print(f"{'':18}{'n':>4}{'Top-1':>8}{'Top-3':>8}{'Top-5':>8}{'MRR':>8}   (strict: đúng ID kể cả sub-technique)")
for lang in ("en", "vi"):
    s = summary["all"][lang]
    print(f"{'Toàn bộ ['+lang+']':18}{s['n']:>4}{s['top1_strict']:>7}%{s['top3_strict']:>7}%{s['top5_strict']:>7}%{s['mrr_strict']:>8}")
print(f"\n{'':18}{'n':>4}{'Top-1':>8}{'Top-3':>8}{'Top-5':>8}   (parent: đúng technique cha, bỏ qua sub-technique)")
for lang in ("en", "vi"):
    s = summary["all"][lang]
    print(f"{'Toàn bộ ['+lang+']':18}{s['n']:>4}{s['top1_parent']:>7}%{s['top3_parent']:>7}%{s['top5_parent']:>7}%")
print("\nTheo nhóm sự cố (Top-5 strict, en / vi):")
for c, v in summary["by_category"].items():
    print(f"  {c:12} n={v['en']['n']:>2}   en {v['en']['top5_strict']:>5}%   vi {v['vi']['top5_strict']:>5}%")
print(f"\nNgẫu nhiên (Top-5): {summary['random_baseline_top5_pct']}%")

misses = [r for r in rows if r["lang"] == "en" and not r["rank_strict"] or (r["lang"] == "en" and r["rank_strict"] and r["rank_strict"] > 5)]
print(f"\nCác câu tiếng Anh trượt Top-5 ({len(misses)}):")
for r in misses[:12]:
    print(f"  {r['id']} mong đợi {r['expected']} | nhận {r['top5'][:2]}")

json.dump({"summary": summary, "rows": rows}, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\nĐã ghi {args.out}")
