import os
from attck_search import build_index, Searcher

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
MODEL_DIR = os.path.join(HERE, "models")

print("Building ATT&CK index (BM25 + procedure examples)...")
version = build_index(DATA_DIR, MODEL_DIR)
print(f"Techniques: {version['technique_count']} | procedure examples: {version['procedure_examples']}")
print(f"Snapshot: {version['version']} | sha256: {version['sha256'][:16]}...")

searcher = Searcher(MODEL_DIR)
print("\n── Test retrieval ──")
for q in ["brute force SSH login attempts from external IP",
          "phishing email with malicious attachment",
          "lateral movement using stolen credentials",
          "nhiều lần đăng nhập thất bại vào tài khoản quản trị"]:
    print(f"\nQuery: '{q}'")
    for r in searcher.search(q, top_k=3):
        print(f"  [{r['rank']}] {r['id']} — {r['name']} (score={r['score']})")
print("\n✓ ATT&CK retrieval engine ready!")
