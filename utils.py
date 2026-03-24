from datetime import datetime, timedelta
import math


# --- 한국 시간(KST) 계산 함수 ---
def get_kst_now():
    return (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")


def get_kst_date():
    return (datetime.utcnow() + timedelta(hours=9)).date()


def calculate_wilson_ci(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    denominator = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denominator
    spread = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator
    return p, max(0.0, center - spread), min(1.0, center + spread)
