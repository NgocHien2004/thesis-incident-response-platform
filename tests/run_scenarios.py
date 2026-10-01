import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.scenarios import scenario1_phishing
from tests.scenarios import scenario2_credential
from tests.scenarios import scenario3_malware
from tests.scenarios import scenario4_webattack

def main():
    print("╔══════════════════════════════════════════╗")
    print("║  CHẠY 4 KỊCH BẢN MÔ PHỎNG SỰ CỐ        ║")
    print("╚══════════════════════════════════════════╝")

    results = []
    scenarios = [
        scenario1_phishing,
        scenario2_credential,
        scenario3_malware,
        scenario4_webattack,
    ]

    for s in scenarios:
        try:
            result = s.run()
            if result:
                results.append(result)
        except Exception as e:
            print(f"  LỖI: {e}")

    print("\n" + "="*60)
    print("KẾT QUẢ TỔNG HỢP")
    print("="*60)
    for r in results:
        print(f"  {r['scenario']:<25} | incident #{r['incident_id']} | triage: {r['triage_time_s']}s | total: {r['total_time_s']}s")

    # Lưu kết quả
    with open("tests/scenario_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nKết quả lưu tại tests/scenario_results.json")

if __name__ == "__main__":
    main()