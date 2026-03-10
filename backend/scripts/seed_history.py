"""
과거 배치 데이터 시드 스크립트

2년치 더미 데이터를 DB에 삽입합니다.
- 히스토리 조회
- AI 질의응답
- 통계 분석용

사용법:
    python -m scripts.seed_history
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.models import Batch, Measurement

# DB 연결
DB_PATH = Path(__file__).parent.parent / "dongchon.db"
engine = create_engine(f"sqlite:///{DB_PATH}")
Session = sessionmaker(bind=engine)

# 설정
CULTIVARS = ["해남", "괴산", "강원", "기타"]
QUALITY_GRADES = ["A", "A", "A", "B", "B", "C"]  # A가 더 많음

SEASON_CONFIG = {
    "봄": {"months": [3, 4, 5], "salinity": (11.0, 12.0), "duration": (14, 18), "temp": (10, 16)},
    "여름": {"months": [6, 7, 8], "salinity": (10.0, 11.0), "duration": (10, 14), "temp": (18, 25)},
    "가을": {"months": [9, 10, 11], "salinity": (11.0, 12.0), "duration": (14, 18), "temp": (8, 15)},
    "겨울": {"months": [12, 1, 2], "salinity": (13.0, 14.0), "duration": (18, 24), "temp": (4, 10)},
}

def get_season(month):
    for season, config in SEASON_CONFIG.items():
        if month in config["months"]:
            return season
    return "겨울"


def generate_batch(session, start_date: datetime, tank_id: int):
    """단일 배치 생성"""
    season = get_season(start_date.month)
    config = SEASON_CONFIG[season]

    duration_hours = random.uniform(*config["duration"])
    end_date = start_date + timedelta(hours=duration_hours)

    batch = Batch(
        tank_id=tank_id,
        status="completed",
        start_time=start_date,
        end_time=end_date,
        cultivar=random.choice(CULTIVARS),
        avg_weight=round(random.uniform(2.5, 4.0), 2),
        firmness=round(random.uniform(40, 65), 1),
        leaf_thickness=round(random.uniform(2, 4), 1),
        total_quantity=round(random.uniform(300, 500), 0),
        room_temp=round(random.uniform(15, 22), 1),
        season=season,
        initial_salinity=round(random.uniform(*config["salinity"]), 1),
        initial_water_temp=round(random.uniform(*config["temp"]), 1),
        final_cabbage_salinity=round(random.uniform(1.5, 2.5), 2),
        bend_test=random.randint(3, 5),
        quality_grade=random.choice(QUALITY_GRADES),
        output_quantity=round(random.uniform(250, 450), 0),
    )

    session.add(batch)
    session.flush()

    # 측정 데이터 생성 (2~3시간 간격)
    num_measurements = int(duration_hours / 2.5) + 1
    initial_sal = float(batch.initial_salinity)

    for i in range(num_measurements):
        hours_elapsed = i * (duration_hours / num_measurements)
        measure_time = start_date + timedelta(hours=hours_elapsed)

        # 염도 감소
        progress = hours_elapsed / duration_hours
        current_sal = initial_sal * (0.3 + 0.7 * (1 - progress))
        diff = random.uniform(0.3, 0.8)

        measurement = Measurement(
            batch_id=batch.id,
            timestamp=measure_time,
            top_salinity=round(current_sal - diff/2, 2),
            bottom_salinity=round(current_sal + diff/2, 2),
            water_temp=round(float(batch.initial_water_temp) + random.uniform(-1, 2), 1),
            ph=round(random.uniform(6.0, 7.0), 2),
            salinity_avg=round(current_sal, 2),
            salinity_diff=round(diff, 2),
        )
        session.add(measurement)

    return batch


def seed_history_data(start_year=2024, end_year=2025):
    """2년치 히스토리 데이터 생성"""
    session = Session()

    try:
        # 기존 완료 배치 확인
        existing = session.query(Batch).filter(Batch.status == "completed").count()
        if existing > 100:
            print(f"이미 {existing}개의 히스토리 데이터가 있습니다.")
            response = input("계속하시겠습니까? (y/N): ")
            if response.lower() != 'y':
                return

        print(f"\n{start_year}~{end_year}년 히스토리 데이터 생성 중...")

        batch_count = 0
        current_date = datetime(start_year, 1, 1, 8, 0)  # 1월 1일 08:00 시작
        end_date = datetime(end_year, 12, 31, 23, 59)

        while current_date < end_date:
            # 하루에 1~2개 배치 (절임조 1,2,3 랜덤)
            daily_batches = random.randint(1, 2)

            for _ in range(daily_batches):
                tank_id = random.randint(1, 3)

                # 시작 시간 약간의 변동
                start_time = current_date + timedelta(hours=random.uniform(0, 4))

                batch = generate_batch(session, start_time, tank_id)
                batch_count += 1

                if batch_count % 100 == 0:
                    print(f"  {batch_count}개 생성 완료...")
                    session.commit()

            # 다음 날로
            current_date += timedelta(days=1)

        session.commit()
        print(f"\n총 {batch_count}개 히스토리 배치 생성 완료!")

        # 통계
        total_measurements = session.query(Measurement).count()
        print(f"총 측정 데이터: {total_measurements}건")

    finally:
        session.close()


def show_stats():
    """통계 출력"""
    session = Session()

    try:
        total = session.query(Batch).count()
        completed = session.query(Batch).filter(Batch.status == "completed").count()
        active = session.query(Batch).filter(Batch.status == "active").count()

        print("\n=== DB 통계 ===")
        print(f"총 배치: {total}건")
        print(f"  - 완료: {completed}건")
        print(f"  - 진행중: {active}건")

        # 품질 분포
        for grade in ["A", "B", "C"]:
            count = session.query(Batch).filter(Batch.quality_grade == grade).count()
            print(f"  - {grade}등급: {count}건")

        measurements = session.query(Measurement).count()
        print(f"\n총 측정: {measurements}건")

    finally:
        session.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="히스토리 데이터 시드")
    parser.add_argument("--seed", action="store_true", help="2년치 데이터 생성")
    parser.add_argument("--stats", action="store_true", help="통계 확인")

    args = parser.parse_args()

    if args.seed:
        seed_history_data()
    elif args.stats:
        show_stats()
    else:
        parser.print_help()
