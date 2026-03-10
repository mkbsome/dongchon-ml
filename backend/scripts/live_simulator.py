"""
라이브 절임조 시뮬레이터

절임조 1,2,3호기의 실시간 데이터를 시뮬레이션합니다.
- 서버 시작 시 활성 배치 생성
- 주기적으로 측정 데이터 추가
- 절임 완료 시 자동 종료 및 새 배치 시작

사용법:
    # 초기 활성 배치 생성
    python -m scripts.live_simulator --init

    # 측정 데이터 추가 (cron으로 주기 실행)
    python -m scripts.live_simulator --update

    # 전체 리셋 (활성 배치 모두 삭제 후 새로 생성)
    python -m scripts.live_simulator --reset
"""

import random
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.models import Tank, Batch, Measurement

# DB 연결
DB_PATH = Path(__file__).parent.parent / "dongchon.db"
engine = create_engine(f"sqlite:///{DB_PATH}")
Session = sessionmaker(bind=engine)

# 시뮬레이션 설정
CULTIVARS = ["해남", "괴산", "강원", "기타"]
SEASONS = {
    1: "겨울", 2: "겨울", 3: "봄", 4: "봄", 5: "봄", 6: "여름",
    7: "여름", 8: "여름", 9: "가을", 10: "가을", 11: "가을", 12: "겨울"
}

# 계절별 설정
SEASON_CONFIG = {
    "봄": {"salinity": (11.0, 12.0), "duration": (14, 18), "temp": (10, 16)},
    "여름": {"salinity": (10.0, 11.0), "duration": (10, 14), "temp": (18, 25)},
    "가을": {"salinity": (11.0, 12.0), "duration": (14, 18), "temp": (8, 15)},
    "겨울": {"salinity": (13.0, 14.0), "duration": (18, 24), "temp": (4, 10)},
}


def get_current_season():
    """현재 계절 반환"""
    return SEASONS[datetime.now().month]


def create_active_batch(session, tank_id: int) -> Batch:
    """새 활성 배치 생성"""
    season = get_current_season()
    config = SEASON_CONFIG[season]

    # 시작 시간: 현재부터 0~12시간 전 랜덤
    hours_ago = random.uniform(0, 12)
    start_time = datetime.now() - timedelta(hours=hours_ago)

    batch = Batch(
        tank_id=tank_id,
        status="active",
        start_time=start_time,
        cultivar=random.choice(CULTIVARS),
        avg_weight=round(random.uniform(2.5, 4.0), 2),
        firmness=round(random.uniform(40, 65), 1),
        leaf_thickness=round(random.uniform(2, 4), 1),
        total_quantity=round(random.uniform(300, 500), 0),
        room_temp=round(random.uniform(15, 22), 1),
        season=season,
        initial_salinity=round(random.uniform(*config["salinity"]), 1),
        initial_water_temp=round(random.uniform(*config["temp"]), 1),
    )

    session.add(batch)
    session.commit()
    session.refresh(batch)

    # 초기 측정 데이터 추가
    add_measurement(session, batch, start_time)

    # 경과 시간에 따른 추가 측정 데이터
    elapsed_hours = hours_ago
    measurement_interval = 2  # 2시간 간격

    for h in range(measurement_interval, int(elapsed_hours), measurement_interval):
        measure_time = start_time + timedelta(hours=h)
        add_measurement(session, batch, measure_time)

    return batch


def add_measurement(session, batch: Batch, timestamp: datetime = None):
    """측정 데이터 추가"""
    if timestamp is None:
        timestamp = datetime.now()

    # 경과 시간 계산
    elapsed_hours = (timestamp - batch.start_time).total_seconds() / 3600

    # 염도 감소 시뮬레이션 (초기 염도에서 점진적 감소)
    initial_sal = float(batch.initial_salinity)
    # 시간에 따른 염도 감소 (지수 감소)
    decay_rate = 0.08  # 감소율
    current_salinity = initial_sal * (0.3 + 0.7 * (1 - min(elapsed_hours / 24, 1)))

    # 상하단 염도 차이 (하단이 더 높음)
    salinity_diff = random.uniform(0.3, 0.8)
    top_salinity = round(current_salinity - salinity_diff / 2, 2)
    bottom_salinity = round(current_salinity + salinity_diff / 2, 2)

    # 수온 변화 (약간의 변동)
    water_temp = float(batch.initial_water_temp) + random.uniform(-1, 2)

    measurement = Measurement(
        batch_id=batch.id,
        timestamp=timestamp,
        top_salinity=max(1.0, top_salinity),
        bottom_salinity=max(1.5, bottom_salinity),
        water_temp=round(water_temp, 1),
        ph=round(random.uniform(6.0, 7.0), 2),
        salinity_avg=round((top_salinity + bottom_salinity) / 2, 2),
        salinity_diff=round(salinity_diff, 2),
    )

    session.add(measurement)
    session.commit()

    return measurement


def check_and_complete_batch(session, batch: Batch) -> bool:
    """배치 완료 여부 확인 및 처리"""
    elapsed_hours = (datetime.now() - batch.start_time).total_seconds() / 3600
    season = batch.season or get_current_season()
    config = SEASON_CONFIG[season]
    expected_duration = random.uniform(*config["duration"])

    if elapsed_hours >= expected_duration:
        # 배치 완료 처리
        batch.status = "completed"
        batch.end_time = datetime.now()
        batch.final_cabbage_salinity = round(random.uniform(1.5, 2.5), 2)
        batch.bend_test = random.randint(3, 5)
        batch.quality_grade = random.choice(["A", "A", "A", "B", "B", "C"])
        batch.output_quantity = float(batch.total_quantity) * random.uniform(0.85, 0.95)
        session.commit()
        return True

    return False


def init_live_batches():
    """초기 활성 배치 생성 (1,2,3호기)"""
    session = Session()

    try:
        # 기존 활성 배치 확인
        active_batches = session.query(Batch).filter(Batch.status == "active").all()

        if active_batches:
            print(f"이미 {len(active_batches)}개의 활성 배치가 있습니다.")
            for b in active_batches:
                tank = session.query(Tank).filter(Tank.id == b.tank_id).first()
                elapsed = (datetime.now() - b.start_time).total_seconds() / 3600
                print(f"  - {tank.name}: {b.cultivar}, {elapsed:.1f}시간 경과")
            return

        # 1,2,3호기 중 랜덤하게 1~3개 활성화
        num_active = random.randint(1, 3)
        active_tanks = random.sample([1, 2, 3], num_active)

        print(f"활성 배치 생성 중... (절임조: {active_tanks})")

        for tank_id in active_tanks:
            batch = create_active_batch(session, tank_id)
            tank = session.query(Tank).filter(Tank.id == tank_id).first()
            print(f"  - {tank.name}: {batch.cultivar} {batch.avg_weight}kg, 초기염도 {batch.initial_salinity}%")

        print(f"\n총 {num_active}개 활성 배치 생성 완료!")

    finally:
        session.close()


def update_live_batches():
    """활성 배치 업데이트 (측정 데이터 추가, 완료 처리)"""
    session = Session()

    try:
        active_batches = session.query(Batch).filter(Batch.status == "active").all()

        if not active_batches:
            print("활성 배치가 없습니다. --init으로 생성하세요.")
            return

        for batch in active_batches:
            tank = session.query(Tank).filter(Tank.id == batch.tank_id).first()

            # 완료 여부 확인
            if check_and_complete_batch(session, batch):
                print(f"  - {tank.name}: 배치 완료! (품질: {batch.quality_grade})")
                # 새 배치 시작 (50% 확률)
                if random.random() > 0.5:
                    new_batch = create_active_batch(session, batch.tank_id)
                    print(f"  - {tank.name}: 새 배치 시작 ({new_batch.cultivar})")
            else:
                # 측정 데이터 추가
                add_measurement(session, batch)
                elapsed = (datetime.now() - batch.start_time).total_seconds() / 3600
                last_m = session.query(Measurement).filter(
                    Measurement.batch_id == batch.id
                ).order_by(Measurement.timestamp.desc()).first()
                print(f"  - {tank.name}: 측정 추가 (경과 {elapsed:.1f}h, 염도 {last_m.salinity_avg}%)")

    finally:
        session.close()


def reset_live_batches():
    """모든 활성 배치 삭제 후 새로 생성"""
    session = Session()

    try:
        # 활성 배치 삭제
        active_batches = session.query(Batch).filter(Batch.status == "active").all()
        for batch in active_batches:
            # 관련 측정 데이터도 삭제
            session.query(Measurement).filter(Measurement.batch_id == batch.id).delete()
            session.delete(batch)

        session.commit()
        print(f"{len(active_batches)}개 활성 배치 삭제 완료")

        # 새로 생성
        init_live_batches()

    finally:
        session.close()


def show_status():
    """현재 상태 출력"""
    session = Session()

    try:
        tanks = session.query(Tank).all()
        print("\n=== 절임조 상태 ===\n")

        for tank in tanks:
            batch = session.query(Batch).filter(
                Batch.tank_id == tank.id,
                Batch.status == "active"
            ).first()

            if batch:
                elapsed = (datetime.now() - batch.start_time).total_seconds() / 3600
                last_m = session.query(Measurement).filter(
                    Measurement.batch_id == batch.id
                ).order_by(Measurement.timestamp.desc()).first()

                salinity = last_m.salinity_avg if last_m else batch.initial_salinity
                print(f"{tank.name}: 가동 중")
                print(f"  품종: {batch.cultivar}, 무게: {batch.avg_weight}kg")
                print(f"  경과: {elapsed:.1f}시간, 현재 염도: {salinity}%")
                print()
            else:
                print(f"{tank.name}: 대기 중\n")

        # 통계
        total_batches = session.query(Batch).count()
        completed = session.query(Batch).filter(Batch.status == "completed").count()
        print(f"=== 통계 ===")
        print(f"총 배치: {total_batches}건 (완료: {completed}건)")

    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="라이브 절임조 시뮬레이터")
    parser.add_argument("--init", action="store_true", help="초기 활성 배치 생성")
    parser.add_argument("--update", action="store_true", help="측정 데이터 업데이트")
    parser.add_argument("--reset", action="store_true", help="리셋 후 새로 생성")
    parser.add_argument("--status", action="store_true", help="현재 상태 확인")

    args = parser.parse_args()

    if args.init:
        init_live_batches()
    elif args.update:
        update_live_batches()
    elif args.reset:
        reset_live_batches()
    elif args.status:
        show_status()
    else:
        parser.print_help()
