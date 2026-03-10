from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime

from ..database import get_db
from ..models.models import Batch, Measurement
from ..schemas.schemas import MeasurementCreate, Measurement as MeasurementSchema

router = APIRouter(prefix="/measurements", tags=["measurements"])


@router.get("/batch/{batch_id}", response_model=list[MeasurementSchema])
def get_measurements_by_batch(batch_id: int, db: Session = Depends(get_db)):
    """특정 배치의 모든 측정 기록 조회"""
    measurements = db.query(Measurement).filter(
        Measurement.batch_id == batch_id
    ).order_by(Measurement.timestamp.asc()).all()

    return measurements


@router.get("/tank/{tank_id}/active", response_model=list[MeasurementSchema])
def get_measurements_for_active_batch(tank_id: int, db: Session = Depends(get_db)):
    """특정 탱크의 활성 배치 측정 기록 조회"""
    active_batch = db.query(Batch).filter(
        and_(Batch.tank_id == tank_id, Batch.status == "active")
    ).first()

    if not active_batch:
        return []

    return db.query(Measurement).filter(
        Measurement.batch_id == active_batch.id
    ).order_by(Measurement.timestamp.asc()).all()


@router.post("/tank/{tank_id}", response_model=MeasurementSchema)
def add_measurement(
    tank_id: int,
    measurement_data: MeasurementCreate,
    db: Session = Depends(get_db)
):
    """활성 배치에 측정 기록 추가"""
    # 활성 배치 찾기
    active_batch = db.query(Batch).filter(
        and_(Batch.tank_id == tank_id, Batch.status == "active")
    ).first()

    if not active_batch:
        raise HTTPException(
            status_code=404,
            detail=f"No active batch found for tank {tank_id}"
        )

    # 파생 변수 계산
    salinity_avg = None
    salinity_diff = None

    if measurement_data.top_salinity is not None and measurement_data.bottom_salinity is not None:
        salinity_avg = (measurement_data.top_salinity + measurement_data.bottom_salinity) / 2
        salinity_diff = measurement_data.top_salinity - measurement_data.bottom_salinity

    # 삼투압 지수 계산 (간단한 프록시)
    osmotic_pressure_index = None
    if salinity_avg is not None and measurement_data.water_temp is not None:
        # 간단한 삼투압 지수: 염도 * (1 + 온도/100)
        osmotic_pressure_index = salinity_avg * (1 + measurement_data.water_temp / 100)

    # 적산 온도 계산 (이전 측정 기록 기반)
    accumulated_temp = measurement_data.accumulated_temp
    if accumulated_temp is None and measurement_data.water_temp is not None:
        # 이전 측정 기록에서 적산 온도 가져오기
        last_measurement = db.query(Measurement).filter(
            Measurement.batch_id == active_batch.id
        ).order_by(Measurement.timestamp.desc()).first()

        if last_measurement and last_measurement.accumulated_temp:
            # 시간 간격 계산 (분 단위)
            time_diff = (datetime.now() - last_measurement.timestamp).total_seconds() / 60
            # 적산 온도 = 이전 적산 온도 + (현재 온도 * 시간(분) / 60)
            accumulated_temp = float(last_measurement.accumulated_temp) + (measurement_data.water_temp * time_diff / 60)
        else:
            accumulated_temp = 0

    # 측정 기록 생성
    new_measurement = Measurement(
        batch_id=active_batch.id,
        top_salinity=measurement_data.top_salinity,
        bottom_salinity=measurement_data.bottom_salinity,
        water_temp=measurement_data.water_temp,
        ph=measurement_data.ph,
        memo=measurement_data.memo,
        salinity_avg=measurement_data.salinity_avg or salinity_avg,
        salinity_diff=measurement_data.salinity_diff or salinity_diff,
        osmotic_pressure_index=measurement_data.osmotic_pressure_index or osmotic_pressure_index,
        accumulated_temp=accumulated_temp
    )

    db.add(new_measurement)
    db.commit()
    db.refresh(new_measurement)

    return new_measurement


@router.get("/{measurement_id}", response_model=MeasurementSchema)
def get_measurement(measurement_id: int, db: Session = Depends(get_db)):
    """측정 기록 단건 조회"""
    measurement = db.query(Measurement).filter(Measurement.id == measurement_id).first()
    if not measurement:
        raise HTTPException(status_code=404, detail="Measurement not found")
    return measurement
