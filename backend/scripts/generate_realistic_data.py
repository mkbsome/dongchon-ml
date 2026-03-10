"""
동촌에프에스 현장 인터뷰 기반 현실적 더미 데이터 생성 스크립트
- 2026.02.20 인터뷰 기반 파라미터 적용
- 하루절임/이틀절임 구분
- 계절별 정확한 염도, 시간, 온도 반영

사용법:
    cd backend
    python -m scripts.generate_realistic_data
"""

import random
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple
import math

# 시드 고정 (재현성)
random.seed(42)


# ============ 인터뷰 기반 설정 상수 ============

# 품종 목록 (v4 데이터정의서 기준)
CULTIVAR_LIST = [
    "불암3호", "불암플러스", "휘파람골드", "휘모리",
    "천고마비", "기운찬", "청명가을", "황금스타", "기타"
]

# 품종별 특성
CULTIVAR_PROFILES = {
    "불암3호": {"weight_mod": 1.0, "firmness_mod": 1.0, "absorption_rate": 1.0},
    "불암플러스": {"weight_mod": 1.05, "firmness_mod": 1.05, "absorption_rate": 0.98},
    "휘파람골드": {"weight_mod": 0.95, "firmness_mod": 1.1, "absorption_rate": 0.95},
    "휘모리": {"weight_mod": 0.98, "firmness_mod": 1.08, "absorption_rate": 0.97},
    "천고마비": {"weight_mod": 1.02, "firmness_mod": 0.95, "absorption_rate": 1.02},
    "기운찬": {"weight_mod": 1.0, "firmness_mod": 1.0, "absorption_rate": 1.0},
    "청명가을": {"weight_mod": 0.95, "firmness_mod": 0.98, "absorption_rate": 1.05},
    "황금스타": {"weight_mod": 0.92, "firmness_mod": 0.95, "absorption_rate": 1.03},
    "기타": {"weight_mod": 1.0, "firmness_mod": 1.0, "absorption_rate": 1.0},
}

# 계절별 설정 (인터뷰 2026.02.20 기반)
SEASON_PROFILES = {
    "겨울": {
        "months": [12, 1, 2],
        "room_temp_range": (20, 24),           # 실내 온도 (히터)
        "outdoor_temp_range": (-5, 10),        # 외부 온도
        "water_temp_range": (8, 12),           # 지하수 온도 "10도 미만"
        "cabbage_weight_range": (3.0, 4.2),    # 겨울 배추 3-4kg+
        "firmness_range": (12, 22),            # 단단함 (N) - 겨울 배추가 두껍고 단단
        "leaf_thickness_range": (3, 5),        # 잎 두께 (mm)
        # 절임 방식별 설정
        "pickling_modes": {
            "이틀절임": {
                "probability": 0.6,            # 이틀절임 60%
                "initial_salinity": (10.0, 11.0),  # 10.5% 기준
                "duration_hours": (40, 48),    # 40-48시간
                "added_salt": (35, 45),        # 웃소금 40kg
            },
            "하루절임": {
                "probability": 0.4,            # 하루절임 40%
                "initial_salinity": (13.5, 14.5),  # 14% 기준
                "duration_hours": (20, 28),    # 20-28시간
                "added_salt": (35, 45),        # 웃소금 40kg
            },
        },
        "cultivar_distribution": {
            "불암3호": 0.2, "불암플러스": 0.2, "휘파람골드": 0.1, "휘모리": 0.1,
            "천고마비": 0.1, "기운찬": 0.1, "청명가을": 0.05, "황금스타": 0.05, "기타": 0.1
        },
        "batches_per_month": (35, 50),  # 김장철
    },
    "봄": {
        "months": [3, 4, 5],
        "room_temp_range": (20, 24),
        "outdoor_temp_range": (10, 22),
        "water_temp_range": (12, 16),          # 여름-겨울 중간
        "cabbage_weight_range": (2.3, 3.0),    # 봄 배추 작음 "2.5kg 정도"
        "firmness_range": (8, 16),             # 덜 단단
        "leaf_thickness_range": (2, 4),
        "pickling_modes": {
            "하루절임": {
                "probability": 1.0,
                "initial_salinity": (12.0, 13.0),  # 봄가을 중간값
                "duration_hours": (24, 32),        # 보간값
                "added_salt": (15, 25),            # 20kg
            },
        },
        "cultivar_distribution": {
            "불암3호": 0.15, "불암플러스": 0.15, "휘파람골드": 0.15, "휘모리": 0.15,
            "천고마비": 0.1, "기운찬": 0.1, "청명가을": 0.1, "황금스타": 0.05, "기타": 0.05
        },
        "batches_per_month": (25, 40),
    },
    "여름": {
        "months": [6, 7, 8],
        "room_temp_range": (22, 26),           # 에어컨
        "outdoor_temp_range": (25, 35),
        "water_temp_range": (20, 24),          # "20도 내외", "22-24도"
        "cabbage_weight_range": (2.3, 3.0),    # 여름도 작음
        "firmness_range": (5, 14),             # 여름 배추 무름
        "leaf_thickness_range": (1, 3),
        "pickling_modes": {
            "하루절임": {
                "probability": 1.0,
                "initial_salinity": (12.5, 13.5),  # 13% 기준
                "duration_hours": (20, 26),        # "20시간 좀 넘게"
                "added_salt": (0, 20),             # 0-20kg (안 넣는 경우도)
            },
        },
        "cultivar_distribution": {
            "불암3호": 0.1, "불암플러스": 0.1, "휘파람골드": 0.2, "휘모리": 0.2,
            "천고마비": 0.1, "기운찬": 0.1, "청명가을": 0.1, "황금스타": 0.05, "기타": 0.05
        },
        "batches_per_month": (20, 35),  # 여름은 수요 감소
    },
    "가을": {
        "months": [9, 10, 11],
        "room_temp_range": (20, 24),
        "outdoor_temp_range": (10, 22),
        "water_temp_range": (12, 18),          # 봄과 비슷, 늦가을은 더 차가움
        "cabbage_weight_range": (2.8, 3.5),    # "3kg 정도" - 평균
        "firmness_range": (10, 18),
        "leaf_thickness_range": (2, 4),
        "pickling_modes": {
            "하루절임": {
                "probability": 0.85,
                "initial_salinity": (12.0, 13.0),
                "duration_hours": (24, 32),
                "added_salt": (15, 25),
            },
            "이틀절임": {
                "probability": 0.15,           # 늦가을에만 일부
                "initial_salinity": (10.5, 11.5),
                "duration_hours": (36, 44),
                "added_salt": (30, 40),
            },
        },
        "cultivar_distribution": {
            "불암3호": 0.2, "불암플러스": 0.2, "휘파람골드": 0.1, "휘모리": 0.1,
            "천고마비": 0.15, "기운찬": 0.1, "청명가을": 0.1, "황금스타": 0.03, "기타": 0.02
        },
        "batches_per_month": (40, 60),  # 김장 준비 피크
    },
}

# 품질 기준 (인터뷰 기반)
QUALITY_CRITERIA = {
    "final_salinity_optimal": (1.7, 1.9),      # 최적
    "final_salinity_good": (1.5, 2.0),         # 좋음 범위
    "final_salinity_acceptable": (1.4, 2.2),   # 양호 범위
    "quality_distribution": {
        "좋음": 0.70,      # 70-80%
        "양호": 0.20,      # ~20%
        "나쁨": 0.10,      # 10%+
    },
}


# ============ 데이터 클래스 ============

@dataclass
class RealisticBatch:
    id: int
    tank_id: int
    status: str
    start_time: str
    end_time: str

    # 배추 특성
    cultivar: str
    cultivar_label: str
    cabbage_size: str
    avg_weight: float
    firmness: float
    leaf_thickness: int
    total_quantity: float

    # 환경 정보
    room_temp: float
    outdoor_temp: float
    season: str
    pickling_type: str
    initial_salinity: float
    initial_water_temp: float
    added_salt: bool
    added_salt_amount: int

    # 결과
    total_duration_minutes: int
    final_salinity: float
    quality_bending: int
    quality_grade: str
    notes: Optional[str]

    # 세척 데이터
    wash_tank1_salinity: float
    wash_tank1_water_temp: float
    wash_tank3_salinity: float
    wash_tank3_water_temp: float


@dataclass
class RealisticMeasurement:
    id: int
    batch_id: int
    measurement_idx: int
    timestamp: str
    elapsed_minutes: int
    salinity_top: float
    salinity_bottom: float
    water_temp: float
    ph: float
    salinity_avg: float
    salinity_diff: float


# ============ 시뮬레이션 함수 ============

def get_season_for_date(date: datetime) -> str:
    """날짜로부터 계절 반환"""
    month = date.month
    for season, profile in SEASON_PROFILES.items():
        if month in profile["months"]:
            return season
    return "가을"


def select_cultivar(season: str) -> Tuple[str, str]:
    """계절별 품종 분포에 따라 품종 선택 (ID, Label)"""
    dist = SEASON_PROFILES[season]["cultivar_distribution"]
    r = random.random()
    cumulative = 0
    for cultivar, prob in dist.items():
        cumulative += prob
        if r <= cumulative:
            # ID 생성 (영문 변환)
            cultivar_id_map = {
                "불암3호": "bulam3", "불암플러스": "bulamplus",
                "휘파람골드": "hwiparam", "휘모리": "hwimori",
                "천고마비": "cheongomabi", "기운찬": "giwunchan",
                "청명가을": "cheongmyung", "황금스타": "hwanggeumstar",
                "기타": "other"
            }
            return cultivar_id_map.get(cultivar, "other"), cultivar
    return "other", "기타"


def select_pickling_mode(season: str) -> Tuple[str, dict]:
    """계절별 절임 방식 선택"""
    modes = SEASON_PROFILES[season]["pickling_modes"]
    r = random.random()
    cumulative = 0
    for mode_name, mode_config in modes.items():
        cumulative += mode_config["probability"]
        if r <= cumulative:
            return mode_name, mode_config
    # 기본값
    return list(modes.keys())[0], list(modes.values())[0]


def get_cabbage_size(weight: float) -> str:
    """무게 기반 크기 등급"""
    if weight < 2.5:
        return "S"
    elif weight < 3.0:
        return "M"
    elif weight < 3.5:
        return "L"
    else:
        return "XL"


def simulate_pickling_process(
    season: str,
    pickling_type: str,
    mode_config: dict,
    cultivar: str,
    avg_weight: float,
    firmness: float,
    leaf_thickness: int,
    initial_salinity: float,
    water_temp: float,
    added_salt_amount: int,
) -> Tuple[int, float, int, str, List[dict]]:
    """
    절임 공정 시뮬레이션 (물리 법칙 기반)

    Returns: (duration_minutes, final_salinity, bending_score, quality_grade, measurements)
    """
    profile = CULTIVAR_PROFILES.get(cultivar, CULTIVAR_PROFILES["기타"])

    # 기본 절임 시간 (분)
    base_duration_min = random.uniform(*mode_config["duration_hours"]) * 60

    # 물리적 요인에 따른 시간 조정
    # 1. 무게: 무거울수록 시간 증가 (3kg 기준)
    weight_factor = 1 + (avg_weight - 3.0) * 0.08

    # 2. 경도: 단단할수록 시간 증가 (15N 기준)
    firmness_factor = 1 + (firmness - 15) * 0.015

    # 3. 수온: 낮을수록 시간 증가 (15°C 기준)
    temp_factor = 1 + (15 - water_temp) * 0.02

    # 4. 품종별 흡수율
    absorption_factor = profile["absorption_rate"]

    # 5. 웃소금 효과: 웃소금 많으면 시간 단축
    salt_factor = 1 - (added_salt_amount / 100) * 0.05

    # 최종 절임 시간
    duration_minutes = int(
        base_duration_min * weight_factor * firmness_factor *
        temp_factor * salt_factor / absorption_factor
    )

    # 시간 제한 (절임 방식별)
    if pickling_type == "이틀절임":
        duration_minutes = max(2400, min(2880, duration_minutes))  # 40-48h
    else:
        duration_minutes = max(1200, min(1920, duration_minutes))  # 20-32h

    duration_hours = duration_minutes / 60

    # 측정 데이터 생성 (2시간 간격, 하루 3회 측정 시뮬레이션)
    measurements = []

    # 염도 변화 시뮬레이션
    current_top_salinity = initial_salinity
    current_bottom_salinity = initial_salinity + random.uniform(0.5, 1.5)

    # 측정 간격 (근무시간 기준: 8시, 12시, 17시)
    if duration_hours <= 24:
        measurement_hours = list(range(0, int(duration_hours) + 1, 2))
    else:
        # 이틀절임: 첫날 3회 + 둘째날 3회
        measurement_hours = [0, 4, 9] + [24, 28, 33] + [int(duration_hours)]

    for idx, hours in enumerate(measurement_hours):
        if hours > duration_hours:
            break

        elapsed_minutes = int(hours * 60)
        progress = hours / duration_hours

        # 삼투압 기반 염도 감소
        # 배추로 염분이 침투하면서 염수 염도 감소
        decay_base = 0.12 * absorption_factor
        decay_rate = decay_base * (water_temp / 15) * (1 + added_salt_amount / 100)

        # 상단/하단 염도 변화 (하단이 더 느리게 감소)
        top_decay = decay_rate * (1 + random.uniform(-0.1, 0.1))
        bottom_decay = decay_rate * 0.7 * (1 + random.uniform(-0.1, 0.1))

        current_top_salinity = max(3.0, initial_salinity - top_decay * hours)
        current_bottom_salinity = max(4.0, initial_salinity + 1.0 - bottom_decay * hours)

        # 수온 변화 (실온 방향으로 수렴)
        room_temp = random.uniform(20, 24)
        current_water_temp = water_temp + (room_temp - water_temp) * (1 - math.exp(-hours / 24))
        current_water_temp += random.uniform(-0.3, 0.3)

        # pH 변화 (약간 감소 - 발효 시작)
        current_ph = 7.0 - progress * 0.4 + random.uniform(-0.1, 0.1)

        salinity_avg = (current_top_salinity + current_bottom_salinity) / 2
        salinity_diff = abs(current_bottom_salinity - current_top_salinity)

        measurements.append({
            "measurement_idx": idx,
            "elapsed_minutes": elapsed_minutes,
            "salinity_top": round(current_top_salinity, 2),
            "salinity_bottom": round(current_bottom_salinity, 2),
            "water_temp": round(current_water_temp, 1),
            "ph": round(current_ph, 2),
            "salinity_avg": round(salinity_avg, 2),
            "salinity_diff": round(salinity_diff, 2),
        })

    # 최종 배추 염도 계산 (목표: 1.5-2.0%)
    # 물리적 요인 반영
    base_final = 1.75  # 최적값 기준

    # 초기 염도 영향
    salinity_effect = (initial_salinity - 12) * 0.03

    # 시간 영향 (최적 시간 대비)
    optimal_duration = (mode_config["duration_hours"][0] + mode_config["duration_hours"][1]) / 2 * 60
    time_deviation = (duration_minutes - optimal_duration) / optimal_duration
    time_effect = time_deviation * 0.15

    # 온도 영향 (높으면 침투 빠름 → 염도 높음)
    temp_effect = (water_temp - 15) * 0.01

    # 배추 특성 영향
    weight_effect = (avg_weight - 3.0) * 0.02
    firmness_effect = (firmness - 15) * 0.01

    final_salinity = base_final + salinity_effect + time_effect + temp_effect - weight_effect + firmness_effect
    final_salinity += random.uniform(-0.15, 0.15)
    final_salinity = round(max(1.2, min(2.4, final_salinity)), 2)

    # 휘어짐 점수 (1-5점)
    # 최적 조건일수록 높은 점수
    bending_base = 3.5

    # 최종 염도가 적정 범위일수록 좋음
    if 1.7 <= final_salinity <= 1.9:
        bending_base += 1.2
    elif 1.5 <= final_salinity <= 2.0:
        bending_base += 0.5
    elif final_salinity < 1.4 or final_salinity > 2.2:
        bending_base -= 1.0

    # 시간 적정성
    if abs(time_deviation) < 0.1:
        bending_base += 0.3
    elif abs(time_deviation) > 0.2:
        bending_base -= 0.3

    bending_score = int(round(max(1, min(5, bending_base + random.uniform(-0.5, 0.5)))))

    # 품질 등급 결정 - 현실적 분포: 좋음 70-80%, 양호 15-20%, 나쁨 5-10%
    # 직접적인 확률 기반 접근

    # 기본 품질 점수 (0-100)
    quality_score = 50

    # 염도 기반 점수 (가장 중요)
    if 1.7 <= final_salinity <= 1.9:
        salinity_quality = 1.0  # 최적
    elif 1.6 <= final_salinity <= 2.0:
        salinity_quality = 0.8  # 양호
    elif 1.5 <= final_salinity <= 2.1:
        salinity_quality = 0.5  # 허용
    elif 1.4 <= final_salinity <= 2.2:
        salinity_quality = 0.2  # 경계
    else:
        salinity_quality = 0.0  # 불량

    # 휘어짐 기반 점수
    bending_quality = (bending_score - 1) / 4.0  # 0.0 ~ 1.0

    # 시간 적정성 점수
    if abs(time_deviation) < 0.1:
        time_quality = 1.0
    elif abs(time_deviation) < 0.2:
        time_quality = 0.7
    elif abs(time_deviation) < 0.3:
        time_quality = 0.4
    else:
        time_quality = 0.1

    # 종합 품질 (가중 평균: 염도 50%, 휘어짐 30%, 시간 20%)
    overall_quality = salinity_quality * 0.5 + bending_quality * 0.3 + time_quality * 0.2

    # 확률 기반 등급 결정 (목표: 좋음 75%, 양호 18%, 나쁨 7%)
    # overall_quality에 따라 확률 조정
    rand = random.random()

    if overall_quality >= 0.8:
        # 고품질: 좋음 80%, 양호 15%, 나쁨 5%
        if rand < 0.80:
            quality_grade = "좋음"
        elif rand < 0.95:
            quality_grade = "양호"
        else:
            quality_grade = "나쁨"
    elif overall_quality >= 0.6:
        # 중상품질: 좋음 60%, 양호 30%, 나쁨 10%
        if rand < 0.60:
            quality_grade = "좋음"
        elif rand < 0.90:
            quality_grade = "양호"
        else:
            quality_grade = "나쁨"
    elif overall_quality >= 0.4:
        # 중품질: 좋음 35%, 양호 45%, 나쁨 20%
        if rand < 0.35:
            quality_grade = "좋음"
        elif rand < 0.80:
            quality_grade = "양호"
        else:
            quality_grade = "나쁨"
    elif overall_quality >= 0.2:
        # 중하품질: 좋음 10%, 양호 40%, 나쁨 50%
        if rand < 0.10:
            quality_grade = "좋음"
        elif rand < 0.50:
            quality_grade = "양호"
        else:
            quality_grade = "나쁨"
    else:
        # 저품질: 좋음 0%, 양호 20%, 나쁨 80%
        if rand < 0.00:
            quality_grade = "좋음"
        elif rand < 0.20:
            quality_grade = "양호"
        else:
            quality_grade = "나쁨"

    return duration_minutes, final_salinity, bending_score, quality_grade, measurements


def generate_wash_data(final_salinity: float, water_temp: float) -> dict:
    """세척 데이터 생성"""
    # 1차 세척조: 염분 많이 남음
    wash1_salinity = round(0.8 + random.uniform(0.2, 0.6), 2)
    wash1_temp = round(water_temp + random.uniform(-2, 2), 1)

    # 3차 세척조: 거의 맹물
    wash3_salinity = round(0.1 + random.uniform(0.05, 0.2), 2)
    wash3_temp = round(water_temp + random.uniform(-2, 2), 1)

    return {
        "wash_tank1_salinity": wash1_salinity,
        "wash_tank1_water_temp": wash1_temp,
        "wash_tank3_salinity": wash3_salinity,
        "wash_tank3_water_temp": wash3_temp,
    }


def generate_notes(quality_grade: str, final_salinity: float, pickling_type: str) -> Optional[str]:
    """메모 생성"""
    if quality_grade == "나쁨":
        if final_salinity < 1.5:
            return random.choice(["절임 부족", "추가 절임 필요", "염도 미달"])
        elif final_salinity > 2.0:
            return random.choice(["과절임", "염도 초과", "짠맛 강함"])
        else:
            return random.choice(["무름 현상", "불균일 절임", "작업 조건 불량"])
    elif quality_grade == "좋음" and random.random() < 0.1:
        return random.choice(["최상 품질", "균일 절임", "정상 진행"])
    return None


def generate_two_years_data() -> Tuple[List[dict], List[dict]]:
    """2년치 데이터 생성 (2024-2025)"""
    batches = []
    measurements = []

    batch_id = 1
    measurement_id = 1

    for year in [2024, 2025]:
        current_date = datetime(year, 1, 1, 8, 0, 0)
        year_end = datetime(year, 12, 31, 23, 59, 59)

        while current_date < year_end:
            season = get_season_for_date(current_date)
            season_profile = SEASON_PROFILES[season]

            # 월별 배치 수
            month_batches = random.randint(*season_profile["batches_per_month"])

            for _ in range(month_batches):
                # 월 체크
                if current_date.month != (current_date + timedelta(days=1)).month:
                    break
                if current_date >= year_end:
                    break

                # 탱크 선택 (1-7)
                tank_id = random.randint(1, 7)

                # 품종 선택
                cultivar_id, cultivar_label = select_cultivar(season)
                cultivar_profile = CULTIVAR_PROFILES.get(cultivar_label, CULTIVAR_PROFILES["기타"])

                # 절임 방식 선택
                pickling_type, mode_config = select_pickling_mode(season)

                # 배추 특성
                base_weight = random.uniform(*season_profile["cabbage_weight_range"])
                avg_weight = round(base_weight * cultivar_profile["weight_mod"], 2)

                base_firmness = random.uniform(*season_profile["firmness_range"])
                firmness = round(base_firmness * cultivar_profile["firmness_mod"], 1)

                leaf_thickness = random.randint(*season_profile["leaf_thickness_range"])

                cabbage_size = get_cabbage_size(avg_weight)
                total_quantity = round(random.uniform(400, 700), 0)

                # 환경 조건
                room_temp = round(random.uniform(*season_profile["room_temp_range"]), 1)
                outdoor_temp = round(random.uniform(*season_profile["outdoor_temp_range"]), 1)
                water_temp = round(random.uniform(*season_profile["water_temp_range"]), 1)

                # 염도 및 웃소금
                initial_salinity = round(random.uniform(*mode_config["initial_salinity"]), 1)
                added_salt_range = mode_config["added_salt"]

                # 웃소금 사용 여부 (여름에는 0kg일 수도)
                if added_salt_range[0] == 0:
                    added_salt = random.random() > 0.3  # 70% 사용
                    added_salt_amount = random.randint(15, 25) if added_salt else 0
                else:
                    added_salt = True
                    added_salt_amount = random.randint(*added_salt_range)

                # 공정 시뮬레이션
                duration_minutes, final_salinity, bending_score, quality_grade, meas_data = simulate_pickling_process(
                    season=season,
                    pickling_type=pickling_type,
                    mode_config=mode_config,
                    cultivar=cultivar_label,
                    avg_weight=avg_weight,
                    firmness=firmness,
                    leaf_thickness=leaf_thickness,
                    initial_salinity=initial_salinity,
                    water_temp=water_temp,
                    added_salt_amount=added_salt_amount,
                )

                # 시작/종료 시간
                start_time = current_date
                end_time = start_time + timedelta(minutes=duration_minutes)

                # 세척 데이터
                wash_data = generate_wash_data(final_salinity, water_temp)

                # 메모
                notes = generate_notes(quality_grade, final_salinity, pickling_type)

                # 배치 생성
                batch = RealisticBatch(
                    id=batch_id,
                    tank_id=tank_id,
                    status="completed",
                    start_time=start_time.isoformat(),
                    end_time=end_time.isoformat(),
                    cultivar=cultivar_id,
                    cultivar_label=cultivar_label,
                    cabbage_size=cabbage_size,
                    avg_weight=avg_weight,
                    firmness=firmness,
                    leaf_thickness=leaf_thickness,
                    total_quantity=total_quantity,
                    room_temp=room_temp,
                    outdoor_temp=outdoor_temp,
                    season=season,
                    pickling_type=pickling_type,
                    initial_salinity=initial_salinity,
                    initial_water_temp=water_temp,
                    added_salt=added_salt,
                    added_salt_amount=added_salt_amount,
                    total_duration_minutes=duration_minutes,
                    final_salinity=final_salinity,
                    quality_bending=bending_score,
                    quality_grade=quality_grade,
                    notes=notes,
                    **wash_data
                )
                batches.append(asdict(batch))

                # 측정 데이터
                for meas in meas_data:
                    meas_time = start_time + timedelta(minutes=meas["elapsed_minutes"])

                    measurement = RealisticMeasurement(
                        id=measurement_id,
                        batch_id=batch_id,
                        measurement_idx=meas["measurement_idx"],
                        timestamp=meas_time.isoformat(),
                        elapsed_minutes=meas["elapsed_minutes"],
                        salinity_top=meas["salinity_top"],
                        salinity_bottom=meas["salinity_bottom"],
                        water_temp=meas["water_temp"],
                        ph=meas["ph"],
                        salinity_avg=meas["salinity_avg"],
                        salinity_diff=meas["salinity_diff"],
                    )
                    measurements.append(asdict(measurement))
                    measurement_id += 1

                batch_id += 1

                # 다음 배치 (절임 시간 고려)
                next_gap_days = 2.0 if pickling_type == "이틀절임" else 1.0
                next_gap_days += random.uniform(-0.3, 0.5)
                current_date += timedelta(days=next_gap_days)

                # 근무 시간대 조정 (오전 8시 ~ 오후 6시)
                hour = random.randint(8, 14)
                current_date = current_date.replace(hour=hour, minute=random.randint(0, 59))

            # 다음 달
            if current_date.month == 12:
                current_date = datetime(current_date.year + 1, 1, 1, 8, 0, 0)
            else:
                current_date = datetime(current_date.year, current_date.month + 1, 1, 8, 0, 0)

    return batches, measurements


def print_statistics(batches: List[dict], measurements: List[dict]):
    """통계 출력"""
    print("\n" + "=" * 70)
    print("[통계] 현실적 더미 데이터 (인터뷰 2026.02.20 기반)")
    print("=" * 70)

    print(f"\n총 배치 수: {len(batches)}")
    print(f"총 측정 기록 수: {len(measurements)}")

    # 계절별
    print("\n[계절별] 배치 수:")
    season_counts = {}
    for b in batches:
        season = b["season"]
        season_counts[season] = season_counts.get(season, 0) + 1
    for season in ["봄", "여름", "가을", "겨울"]:
        count = season_counts.get(season, 0)
        print(f"  {season}: {count}개 ({count/len(batches)*100:.1f}%)")

    # 절임 방식별
    print("\n[절임 방식별]:")
    pickling_counts = {}
    for b in batches:
        pt = b["pickling_type"]
        pickling_counts[pt] = pickling_counts.get(pt, 0) + 1
    for pt, count in sorted(pickling_counts.items(), key=lambda x: -x[1]):
        print(f"  {pt}: {count}개 ({count/len(batches)*100:.1f}%)")

    # 품질 등급별
    print("\n[품질 등급별]:")
    grade_counts = {}
    for b in batches:
        grade = b["quality_grade"]
        grade_counts[grade] = grade_counts.get(grade, 0) + 1
    for grade in ["좋음", "양호", "나쁨"]:
        count = grade_counts.get(grade, 0)
        print(f"  {grade}: {count}개 ({count/len(batches)*100:.1f}%)")

    # 평균값
    print("\n[평균값]:")
    avg_weight = sum(b["avg_weight"] for b in batches) / len(batches)
    avg_duration = sum(b["total_duration_minutes"] for b in batches) / len(batches) / 60
    avg_final_salinity = sum(b["final_salinity"] for b in batches) / len(batches)
    avg_initial_salinity = sum(b["initial_salinity"] for b in batches) / len(batches)

    print(f"  평균 배추 무게: {avg_weight:.2f} kg")
    print(f"  평균 절임 시간: {avg_duration:.1f} 시간")
    print(f"  평균 초기 염도: {avg_initial_salinity:.1f}%")
    print(f"  평균 최종 염도: {avg_final_salinity:.2f}%")

    # 계절별 상세
    print("\n[계절별 상세 통계]:")
    for season in ["봄", "여름", "가을", "겨울"]:
        season_batches = [b for b in batches if b["season"] == season]
        if season_batches:
            s_duration = sum(b["total_duration_minutes"] for b in season_batches) / len(season_batches) / 60
            s_salinity = sum(b["initial_salinity"] for b in season_batches) / len(season_batches)
            s_final = sum(b["final_salinity"] for b in season_batches) / len(season_batches)
            s_good = sum(1 for b in season_batches if b["quality_grade"] == "좋음") / len(season_batches) * 100
            print(f"  {season}: 시간 {s_duration:.1f}h, 초기염도 {s_salinity:.1f}%, 최종염도 {s_final:.2f}%, 좋음 {s_good:.0f}%")

    print("\n" + "=" * 70)


def main():
    print("[시작] 동촌에프에스 2년치 현실적 더미 데이터 생성...")
    print("  - 기반: 현장 인터뷰 (2026.02.20)")
    print("  - 절임 방식: 하루절임/이틀절임 구분")
    print("  - 물리 기반 시뮬레이션 적용")

    # 데이터 생성
    batches, measurements = generate_two_years_data()

    # 통계 출력
    print_statistics(batches, measurements)

    # JSON 저장
    output_data = {
        "generated_at": datetime.now().isoformat(),
        "source": "interview_20260220",
        "years": [2024, 2025],
        "total_batches": len(batches),
        "total_measurements": len(measurements),
        "batches": batches,
        "measurements": measurements
    }

    json_path = "scripts/realistic_data_2024_2025.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"\n[완료] JSON 저장: {json_path}")

    # CSV 저장 (batches_summary)
    import csv

    csv_batches_path = "scripts/batches_summary_realistic.csv"
    if batches:
        with open(csv_batches_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=batches[0].keys())
            writer.writeheader()
            writer.writerows(batches)
        print(f"[완료] CSV 저장: {csv_batches_path}")

    csv_meas_path = "scripts/measurements_realistic.csv"
    if measurements:
        with open(csv_meas_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=measurements[0].keys())
            writer.writeheader()
            writer.writerows(measurements)
        print(f"[완료] CSV 저장: {csv_meas_path}")

    print(f"\n[요약]")
    print(f"  - 배치: {len(batches)}개")
    print(f"  - 측정 기록: {len(measurements)}개")


if __name__ == "__main__":
    main()
