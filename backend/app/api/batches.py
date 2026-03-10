from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from typing import Optional

from ..database import get_db
from ..models.models import Batch, Measurement
from ..schemas.schemas import (
    BatchCreate, BatchFinish, Batch as BatchSchema,
    BatchWithMeasurements, ActiveBatchResponse
)

router = APIRouter(prefix="/batches", tags=["batches"])


@router.get("/", response_model=list[BatchSchema])
def get_batches(
    status: Optional[str] = None,
    tank_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """모든 배치 조회 (필터링 가능)"""
    query = db.query(Batch)

    if status:
        query = query.filter(Batch.status == status)
    if tank_id:
        query = query.filter(Batch.tank_id == tank_id)

    return query.order_by(Batch.start_time.desc()).offset(skip).limit(limit).all()


@router.get("/active", response_model=list[BatchSchema])
def get_active_batches(db: Session = Depends(get_db)):
    """모든 활성 배치 조회"""
    return db.query(Batch).filter(Batch.status == "active").all()


@router.get("/active/{tank_id}", response_model=ActiveBatchResponse)
def get_active_batch_by_tank(tank_id: int, db: Session = Depends(get_db)):
    """특정 탱크의 활성 배치 조회"""
    batch = db.query(Batch).filter(
        and_(Batch.tank_id == tank_id, Batch.status == "active")
    ).first()

    return ActiveBatchResponse(tank_id=tank_id, batch=batch)


@router.get("/{batch_id}", response_model=BatchWithMeasurements)
def get_batch(batch_id: int, db: Session = Depends(get_db)):
    """배치 상세 조회 (측정 기록 포함)"""
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


@router.post("/", response_model=BatchSchema)
def create_batch(batch_data: BatchCreate, db: Session = Depends(get_db)):
    """새 배치 생성 (해당 탱크의 기존 활성 배치는 자동 종료)"""
    # 해당 탱크의 기존 활성 배치 종료
    existing_active = db.query(Batch).filter(
        and_(Batch.tank_id == batch_data.tank_id, Batch.status == "active")
    ).first()

    if existing_active:
        existing_active.status = "completed"
        existing_active.end_time = datetime.now()

    # 계절 자동 판단 (입력 안 된 경우)
    season = batch_data.season
    if not season:
        month = datetime.now().month
        if 3 <= month <= 5:
            season = "봄"
        elif 6 <= month <= 8:
            season = "여름"
        elif 9 <= month <= 11:
            season = "가을"
        else:
            season = "겨울"

    # 새 배치 생성
    new_batch = Batch(
        tank_id=batch_data.tank_id,
        status="active",
        cultivar=batch_data.cultivar,
        avg_weight=batch_data.avg_weight,
        firmness=batch_data.firmness,
        leaf_thickness=batch_data.leaf_thickness,
        total_quantity=batch_data.total_quantity,
        room_temp=batch_data.room_temp,
        season=season,
        initial_salinity=batch_data.initial_salinity,
        initial_water_temp=batch_data.initial_water_temp
    )

    db.add(new_batch)
    db.commit()
    db.refresh(new_batch)

    return new_batch


@router.put("/{tank_id}/finish", response_model=BatchSchema)
def finish_batch(tank_id: int, finish_data: BatchFinish, db: Session = Depends(get_db)):
    """배치 종료 (결과 데이터 입력)"""
    batch = db.query(Batch).filter(
        and_(Batch.tank_id == tank_id, Batch.status == "active")
    ).first()

    if not batch:
        raise HTTPException(status_code=404, detail="No active batch found for this tank")

    # 결과 데이터 업데이트
    batch.status = "completed"
    batch.end_time = datetime.now()
    batch.final_cabbage_salinity = finish_data.final_cabbage_salinity
    batch.bend_test = finish_data.bend_test
    batch.output_quantity = finish_data.output_quantity
    batch.quality_grade = finish_data.quality_grade
    batch.notes = finish_data.notes

    # 세척 데이터
    batch.wash1_top_salinity = finish_data.wash1_top_salinity
    batch.wash1_bottom_salinity = finish_data.wash1_bottom_salinity
    batch.wash1_water_temp = finish_data.wash1_water_temp
    batch.wash2_top_salinity = finish_data.wash2_top_salinity
    batch.wash2_bottom_salinity = finish_data.wash2_bottom_salinity
    batch.wash2_water_temp = finish_data.wash2_water_temp
    batch.wash3_top_salinity = finish_data.wash3_top_salinity
    batch.wash3_bottom_salinity = finish_data.wash3_bottom_salinity
    batch.wash3_water_temp = finish_data.wash3_water_temp

    db.commit()
    db.refresh(batch)

    return batch
