from anomaly_agent.model import AnomalyDetector
from anomaly_agent.severity import classify_severity

detector = AnomalyDetector.load()
t = detector.thresholds

print("=== SEUILS ===")
print(f"anomaly  = {t.anomaly:.6f}")
print(f"medium   = {t.medium:.6f}")
print(f"high     = {t.high:.6f}")
print(f"critical = {t.critical:.6f}")

tests = [
    ("NORMAL", t.anomaly * 0.99, None),
    ("LOW", (t.anomaly + t.medium) / 2, "low"),
    ("MEDIUM", (t.medium + t.high) / 2, "medium"),
    ("HIGH", (t.high + t.critical) / 2, "high"),
    ("CRITICAL", t.critical * 1.01, "critical"),
]

print("\n=== TEST SEVERITY ===")

all_pass = True

for name, score, expected in tests:
    result = classify_severity(score, t)
    status = "PASS" if result == expected else "FAIL"

    if status == "FAIL":
        all_pass = False

    print(
        f"{name:10} "
        f"score={score:.6f} "
        f"-> {result} "
        f"| expected={expected} "
        f"| {status}"
    )

print("\nSTATUS:", "PASS" if all_pass else "FAIL")