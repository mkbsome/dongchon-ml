"""
1년치 더미 데이터 생성 스크립트
- 계절별 배추 특성 반영
- 날씨/온도에 따른 절임 시간 변화
- 현실적인 측정 데이터 시뮬레이션
- 품질 결과 반영

사용법:
    cd backend
    python -m scripts.generate_dummy_data
"""

import random
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional
import math

# 시드 고정 (재현성)
random.seed(42)


# ============ 설정 상수 ============

# 품종별 특성
CULTIVAR_PROFILES = {
    "해남": {
        "avg_weight_range": (2.5, 3.5),      # kg
        "firmness_range": (45, 60),           # 센서값
        "leaf_thickness_range": (2.5, 3.5),   # 1-5 스케일
        "salt_absorption_rate": 1.0,          # 기준
        "quality_tendency": 0.85,             # A등급 기본 확률
    },
    "괴산": {
        "avg_weight_range": (2.8, 4.0),
        "firmness_range": (50, 65),
        "leaf_thickness_range": (3.0, 4.0),
        "salt_absorption_rate": 0.95,
        "quality_tendency": 0.80,
    },
    "강원": {
        "avg_weight_range": (2.2, 3.2),
        "firmness_range": (40, 55),
        "leaf_thickness_range": (2.0, 3.0),
        "salt_absorption_rate": 1.05,
        "quality_tendency": 0.82,
    },
    "기타": {
        "avg_weight_range": (2.5, 3.8),
        "firmness_range": (42, 58),
        "leaf_thickness_range": (2.5, 3.5),
        "salt_absorption_rate": 1.0,
        "quality_tendency": 0.75,
    },
}

# 계절별 설정
SEASON_PROFILES = {
    "봄": {
        "months": [3, 4, 5],
        "room_temp_range": (12, 18),
        "water_temp_range": (10, 16),
        "base_salinity": 11.5,
        "base_duration_hours": 14,
        "cultivar_distribution": {"해남": 0.3, "괴산": 0.3, "강원": 0.2, "기타": 0.2},
        "batches_per_month": (25, 35),  # 월간 배치 수 범위
    },
    "여름": {
        "months": [6, 7, 8],
        "room_temp_range": (22, 30),
        "water_temp_range": (18, 25),
        "base_salinity": 10.5,
        "base_duration_hours": 10,
        "cultivar_distribution": {"해남": 0.4, "괴산": 0.2, "강원": 0.1, "기타": 0.3},
        "batches_per_month": (15, 25),  # 여름은 절임 배추 수요 감소
    },
    "가을": {
        "months": [9, 10, 11],
        "room_temp_range": (10, 18),
        "water_temp_range": (8, 15),
        "base_salinity": 11.5,
        "base_duration_hours": 14,
        "cultivar_distribution": {"해남": 0.35, "괴산": 0.35, "강원": 0.2, "기타": 0.1},
        "batches_per_month": (40, 55),  # 김장철 피크
    },
    "겨울": {
        "months": [12, 1, 2],
        "room_temp_range": (5, 12),
        "water_temp_range": (4, 10),
        "base_salinity": 13.5,
        "base_duration_hours": 18,
        "cultivar_distribution": {"해남": 0.4, "괴산": 0.3, "강원": 0.15, "기타": 0.15},
        "batches_per_month": (30, 45),  # 김장철 후반
    },
}


# ============ 데이터 클래스 ============

@dataclass
class DummyBatch:
    id: int
    tank_id: int
    status: str
    start_time: str
    end_time: Optional[str]

    # 배추 특성
    cultivar: str
    avg_weight: float
    firmness: float
    leaf_thickness: float
    total_quantity: float

    # 환경 정보
    room_temp: float
    season: str
    initial_salinity: float
    initial_water_temp: float

    # 결과
    final_cabbage_salinity: Optional[float]
    bend_test: Optional[float]
    output_quantity: Optional[float]
    quality_grade: Optional[str]
    notes: Optional[str]

    # 세척 데이터
    wash1_top_salinity: Optional[float]
    wash1_bottom_salinity: Optional[float]
    wash1_water_temp: Optional[float]
    wash2_top_salinity: Optional[float]
    wash2_bottom_salinity: Optional[float]
    wash2_water_temp: Optional[float]
    wash3_top_salinity: Optional[float]
    wash3_bottom_salinity: Optional[float]
    wash3_water_temp: Optional[float]


@dataclass
class DummyMeasurement:
    id: int
    batch_id: int
    timestamp: str
    top_salinity: float
    bottom_salinity: float
    water_temp: float
    ph: float
    memo: Optional[str]
    salinity_avg: float
    salinity_diff: float
    osmotic_pressure_index: float
    accumulated_temp: float


# ============ 시뮬레이션 함수 ============

def get_season_for_date(date: datetime) -> str:
    """날짜로부터 계절 반환"""
    month = date.month
    for season, profile in SEASON_PROFILES.items():
        if month in profile["months"]:
            return season
    return "가을"


def select_cultivar(season: str) -> str:
    """계절별 품종 분포에 따라 품종 선택"""
    dist = SEASON_PROFILES[season]["cultivar_distribution"]
    r = random.random()
    cumulative = 0
    for cultivar, prob in dist.items():
        cumulative += prob
        if r <= cumulative:
            return cultivar
    return "기타"


def simulate_pickling_process(
    cultivar: str,
    season: str,
    room_temp: float,
    water_temp: float,
    initial_salinity: float,
    avg_weight: float,
    firmness: float
) -> tuple:
    """
    절임 공정 시뮬레이션
    Returns: (duration_hours, final_salinity, bend_test, quality_grade, measurements_data)
    """
    profile = CULTIVAR_PROFILES[cultivar]
    season_profile = SEASON_PROFILES[season]

    # 기본 절임 시간 계산
    base_duration = season_profile["base_duration_hours"]

    # 무게 영향 (무거울수록 시간 증가)
    weight_factor = avg_weight / 3.0

    # 경도 영향 (단단할수록 시간 증가)
    firmness_factor = 1 + (firmness - 50) / 100

    # 온도 영향 (낮을수록 시간 증가)
    temp_factor = 1.0
    if water_temp < 10:
        temp_factor = 1.3
    elif water_temp < 15:
        temp_factor = 1.1
    elif water_temp > 20:
        temp_factor = 0.85

    # 품종별 흡수율 영향
    absorption_factor = profile["salt_absorption_rate"]

    # 최종 절임 시간 (약간의 랜덤성 추가)
    duration = base_duration * weight_factor * firmness_factor * temp_factor / absorption_factor
    duration *= random.uniform(0.9, 1.1)
    duration = round(max(8, min(24, duration)), 1)

    # 측정 데이터 생성 (2시간 간격)
    measurements_data = []
    num_measurements = int(duration / 2) + 1

    current_top_salinity = initial_salinity
    current_bottom_salinity = initial_salinity + random.uniform(0.5, 1.5)
    accumulated_temp = 0

    for i in range(num_measurements):
        hours_elapsed = i * 2

        # 염도 감소 시뮬레이션 (배추로 스며듦)
        decay_rate = 0.15 * absorption_factor * (water_temp / 15)
        current_top_salinity = max(2.0, current_top_salinity - decay_rate * random.uniform(0.8, 1.2))
        current_bottom_salinity = max(2.5, current_bottom_salinity - decay_rate * 0.8 * random.uniform(0.8, 1.2))

        # 수온 변화 (실온 방향으로 수렴)
        current_water_temp = water_temp + (room_temp - water_temp) * (1 - math.exp(-hours_elapsed / 20))
        current_water_temp += random.uniform(-0.5, 0.5)

        # pH 변화 (약간 감소)
        current_ph = 7.0 - (hours_elapsed / duration) * 0.5 + random.uniform(-0.1, 0.1)

        # 적산 온도
        if i > 0:
            accumulated_temp += (current_water_temp + measurements_data[-1]["water_temp"]) / 2 * 2

        salinity_avg = (current_top_salinity + current_bottom_salinity) / 2
        salinity_diff = abs(current_top_salinity - current_bottom_salinity)
        osmotic_index = salinity_avg * current_water_temp

        measurements_data.append({
            "hours_elapsed": hours_elapsed,
            "top_salinity": round(current_top_salinity, 2),
            "bottom_salinity": round(current_bottom_salinity, 2),
            "water_temp": round(current_water_temp, 1),
            "ph": round(current_ph, 2),
            "salinity_avg": round(salinity_avg, 2),
            "salinity_diff": round(salinity_diff, 2),
            "osmotic_pressure_index": round(osmotic_index, 2),
            "accumulated_temp": round(accumulated_temp, 1),
        })

    # 최종 결과 계산
    final_salinity = round(random.uniform(2.0, 3.0), 1)  # 배추 염도

    # 휘어짐 테스트 (품질 지표)
    # 적절한 시간 + 적절한 염도 = 좋은 휘어짐
    base_bend = 3.5

    # 시간이 적절한지
    optimal_duration = base_duration * weight_factor
    duration_deviation = abs(duration - optimal_duration) / optimal_duration
    if duration_deviation < 0.1:
        base_bend += 1.0
    elif duration_deviation < 0.2:
        base_bend += 0.5
    elif duration_deviation > 0.3:
        base_bend -= 0.5

    # 온도 영향
    if 12 <= water_temp <= 18:
        base_bend += 0.3
    elif water_temp < 8 or water_temp > 22:
        base_bend -= 0.3

    # 랜덤성
    bend_test = base_bend + random.uniform(-0.5, 0.5)
    bend_test = round(max(1.0, min(5.0, bend_test)), 1)

    # 품질 등급 결정
    quality_base = profile["quality_tendency"]

    if bend_test >= 4.0:
        quality_prob = quality_base + 0.1
    elif bend_test >= 3.0:
        quality_prob = quality_base - 0.1
    else:
        quality_prob = quality_base - 0.3

    # 염도 영향
    if 2.0 <= final_salinity <= 2.8:
        quality_prob += 0.05
    elif final_salinity > 3.2:
        quality_prob -= 0.1

    r = random.random()
    if r < quality_prob:
        quality_grade = "A"
    elif r < quality_prob + 0.15:
        quality_grade = "B"
    else:
        quality_grade = "C"

    return duration, final_salinity, bend_test, quality_grade, measurements_data


def generate_wash_data(final_salinity: float, water_temp: float) -> dict:
    """세척 데이터 생성"""
    # 1차 세척: 염도 크게 감소
    wash1_top = round(final_salinity * random.uniform(0.6, 0.7), 2)
    wash1_bottom = round(wash1_top + random.uniform(0.1, 0.3), 2)
    wash1_temp = round(water_temp + random.uniform(-2, 2), 1)

    # 2차 세척: 추가 감소
    wash2_top = round(wash1_top * random.uniform(0.5, 0.6), 2)
    wash2_bottom = round(wash2_top + random.uniform(0.05, 0.15), 2)
    wash2_temp = round(water_temp + random.uniform(-2, 2), 1)

    # 3차 세척: 최종
    wash3_top = round(wash2_top * random.uniform(0.4, 0.5), 2)
    wash3_bottom = round(wash3_top + random.uniform(0.02, 0.08), 2)
    wash3_temp = round(water_temp + random.uniform(-2, 2), 1)

    return {
        "wash1_top_salinity": wash1_top,
        "wash1_bottom_salinity": wash1_bottom,
        "wash1_water_temp": wash1_temp,
        "wash2_top_salinity": wash2_top,
        "wash2_bottom_salinity": wash2_bottom,
        "wash2_water_temp": wash2_temp,
        "wash3_top_salinity": wash3_top,
        "wash3_bottom_salinity": wash3_bottom,
        "wash3_water_temp": wash3_temp,
    }


def generate_year_data(year: int = 2024) -> tuple:
    """1년치 데이터 생성"""
    batches = []
    measurements = []

    batch_id = 1
    measurement_id = 1

    # 1월부터 12월까지
    current_date = datetime(year, 1, 1, 8, 0, 0)  # 오전 8시 시작
    end_date = datetime(year, 12, 31, 23, 59, 59)

    while current_date < end_date:
        season = get_season_for_date(current_date)
        season_profile = SEASON_PROFILES[season]

        # 이번 달 배치 수 결정
        month_batches = random.randint(*season_profile["batches_per_month"])

        # 이번 달 내에서 배치 분산
        days_in_month = 28 if current_date.month == 2 else (30 if current_date.month in [4, 6, 9, 11] else 31)

        for _ in range(month_batches):
            if current_date.month != (current_date + timedelta(days=1)).month:
                break

            # 탱크 선택 (1-3)
            tank_id = random.randint(1, 3)

            # 품종 선택
            cultivar = select_cultivar(season)
            profile = CULTIVAR_PROFILES[cultivar]

            # 배추 특성
            avg_weight = round(random.uniform(*profile["avg_weight_range"]), 2)
            firmness = round(random.uniform(*profile["firmness_range"]), 1)
            leaf_thickness = round(random.uniform(*profile["leaf_thickness_range"]), 1)
            total_quantity = round(random.uniform(400, 800), 0)

            # 환경 조건
            room_temp = round(random.uniform(*season_profile["room_temp_range"]), 1)
            water_temp = round(random.uniform(*season_profile["water_temp_range"]), 1)
            initial_salinity = round(season_profile["base_salinity"] + random.uniform(-1, 1), 1)

            # 공정 시뮬레이션
            duration, final_salinity, bend_test, quality_grade, meas_data = simulate_pickling_process(
                cultivar, season, room_temp, water_temp, initial_salinity, avg_weight, firmness
            )

            # 시작/종료 시간
            start_time = current_date
            end_time = start_time + timedelta(hours=duration)

            # 세척 데이터
            wash_data = generate_wash_data(final_salinity, water_temp)

            # 출하량 (손실 5-15%)
            output_quantity = round(total_quantity * random.uniform(0.85, 0.95), 0)

            # 메모 생성
            notes = None
            if quality_grade == "C":
                notes = random.choice([
                    "무름 현상 발생",
                    "과절임 주의",
                    "염도 조절 필요",
                    "온도 관리 미흡"
                ])
            elif random.random() < 0.1:
                notes = random.choice([
                    "정상 진행",
                    "품질 양호",
                    "신선도 우수"
                ])

            # 배치 생성
            batch = DummyBatch(
                id=batch_id,
                tank_id=tank_id,
                status="completed",
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                cultivar=cultivar,
                avg_weight=avg_weight,
                firmness=firmness,
                leaf_thickness=leaf_thickness,
                total_quantity=total_quantity,
                room_temp=room_temp,
                season=season,
                initial_salinity=initial_salinity,
                initial_water_temp=water_temp,
                final_cabbage_salinity=final_salinity,
                bend_test=bend_test,
                output_quantity=output_quantity,
                quality_grade=quality_grade,
                notes=notes,
                **wash_data
            )
            batches.append(asdict(batch))

            # 측정 데이터 생성
            for meas in meas_data:
                meas_time = start_time + timedelta(hours=meas["hours_elapsed"])

                measurement = DummyMeasurement(
                    id=measurement_id,
                    batch_id=batch_id,
                    timestamp=meas_time.isoformat(),
                    top_salinity=meas["top_salinity"],
                    bottom_salinity=meas["bottom_salinity"],
                    water_temp=meas["water_temp"],
                    ph=meas["ph"],
                    memo=None,
                    salinity_avg=meas["salinity_avg"],
                    salinity_diff=meas["salinity_diff"],
                    osmotic_pressure_index=meas["osmotic_pressure_index"],
                    accumulated_temp=meas["accumulated_temp"],
                )
                measurements.append(asdict(measurement))
                measurement_id += 1

            batch_id += 1

            # 다음 배치 시작 시간 (1-3일 후)
            current_date += timedelta(days=random.uniform(0.5, 2.5))

            # 작업 시간대 조정 (오전 6시 ~ 오후 6시)
            hour = random.randint(6, 18)
            current_date = current_date.replace(hour=hour, minute=random.randint(0, 59))

        # 다음 달로 이동
        if current_date.month == 12:
            current_date = datetime(current_date.year + 1, 1, 1, 8, 0, 0)
        else:
            current_date = datetime(current_date.year, current_date.month + 1, 1, 8, 0, 0)

    return batches, measurements


def print_statistics(batches: List[dict], measurements: List[dict]):
    """통계 출력"""
    print("\n" + "="*60)
    print("[통계] 생성된 더미 데이터")
    print("="*60)

    print(f"\n총 배치 수: {len(batches)}")
    print(f"총 측정 기록 수: {len(measurements)}")

    # 계절별 통계
    print("\n[계절별] 배치 수:")
    season_counts = {}
    for b in batches:
        season = b["season"]
        season_counts[season] = season_counts.get(season, 0) + 1
    for season, count in season_counts.items():
        print(f"  {season}: {count}개")

    # 품종별 통계
    print("\n[품종별] 배치 수:")
    cultivar_counts = {}
    for b in batches:
        cultivar = b["cultivar"]
        cultivar_counts[cultivar] = cultivar_counts.get(cultivar, 0) + 1
    for cultivar, count in sorted(cultivar_counts.items(), key=lambda x: -x[1]):
        print(f"  {cultivar}: {count}개 ({count/len(batches)*100:.1f}%)")

    # 품질 등급별 통계
    print("\n[품질등급별]:")
    grade_counts = {}
    for b in batches:
        grade = b["quality_grade"]
        grade_counts[grade] = grade_counts.get(grade, 0) + 1
    for grade in ["A", "B", "C"]:
        count = grade_counts.get(grade, 0)
        print(f"  {grade}등급: {count}개 ({count/len(batches)*100:.1f}%)")

    # 평균값들
    print("\n[평균값]:")
    avg_weight = sum(b["avg_weight"] for b in batches) / len(batches)
    avg_duration = sum(
        (datetime.fromisoformat(b["end_time"]) - datetime.fromisoformat(b["start_time"])).total_seconds() / 3600
        for b in batches
    ) / len(batches)
    avg_bend = sum(b["bend_test"] for b in batches) / len(batches)

    print(f"  평균 무게: {avg_weight:.2f} kg")
    print(f"  평균 절임 시간: {avg_duration:.1f} 시간")
    print(f"  평균 휘어짐 점수: {avg_bend:.2f}")

    print("\n" + "="*60)


def main():
    print("[시작] 동촌에프에스 1년치 더미 데이터 생성...")

    # 데이터 생성
    batches, measurements = generate_year_data(2024)

    # 통계 출력
    print_statistics(batches, measurements)

    # JSON 파일로 저장
    output_data = {
        "generated_at": datetime.now().isoformat(),
        "year": 2024,
        "batches": batches,
        "measurements": measurements
    }

    output_path = "scripts/dummy_data_2024.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n[완료] 데이터 저장: {output_path}")
    print(f"   - 배치: {len(batches)}개")
    print(f"   - 측정 기록: {len(measurements)}개")

    # SQL INSERT 문 생성
    sql_path = "scripts/insert_dummy_data.sql"
    with open(sql_path, "w", encoding="utf-8") as f:
        f.write("-- 동촌에프에스 1년치 더미 데이터 INSERT\n")
        f.write(f"-- 생성일: {datetime.now().isoformat()}\n\n")

        f.write("-- 배치 데이터\n")
        for b in batches:
            f.write(f"""INSERT INTO batches (
    tank_id, status, start_time, end_time,
    cultivar, avg_weight, firmness, leaf_thickness, total_quantity,
    room_temp, season, initial_salinity, initial_water_temp,
    final_cabbage_salinity, bend_test, output_quantity, quality_grade, notes,
    wash1_top_salinity, wash1_bottom_salinity, wash1_water_temp,
    wash2_top_salinity, wash2_bottom_salinity, wash2_water_temp,
    wash3_top_salinity, wash3_bottom_salinity, wash3_water_temp
) VALUES (
    {b['tank_id']}, '{b['status']}', '{b['start_time']}', '{b['end_time']}',
    '{b['cultivar']}', {b['avg_weight']}, {b['firmness']}, {b['leaf_thickness']}, {b['total_quantity']},
    {b['room_temp']}, '{b['season']}', {b['initial_salinity']}, {b['initial_water_temp']},
    {b['final_cabbage_salinity']}, {b['bend_test']}, {b['output_quantity']}, '{b['quality_grade']}', {f"'{b['notes']}'" if b['notes'] else 'NULL'},
    {b['wash1_top_salinity']}, {b['wash1_bottom_salinity']}, {b['wash1_water_temp']},
    {b['wash2_top_salinity']}, {b['wash2_bottom_salinity']}, {b['wash2_water_temp']},
    {b['wash3_top_salinity']}, {b['wash3_bottom_salinity']}, {b['wash3_water_temp']}
);\n""")

        f.write("\n-- 측정 데이터\n")
        for m in measurements:
            f.write(f"""INSERT INTO measurements (
    batch_id, timestamp, top_salinity, bottom_salinity, water_temp, ph,
    salinity_avg, salinity_diff, osmotic_pressure_index, accumulated_temp
) VALUES (
    {m['batch_id']}, '{m['timestamp']}', {m['top_salinity']}, {m['bottom_salinity']}, {m['water_temp']}, {m['ph']},
    {m['salinity_avg']}, {m['salinity_diff']}, {m['osmotic_pressure_index']}, {m['accumulated_temp']}
);\n""")

    print(f"[완료] SQL 파일 저장: {sql_path}")


if __name__ == "__main__":
    main()
