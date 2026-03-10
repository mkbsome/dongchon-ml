from pydantic import BaseModel
from datetime import datetime
from typing import Optional


# ============ Tank Schemas ============
class TankBase(BaseModel):
    name: str
    capacity: Optional[float] = None
    is_active: bool = True


class TankCreate(TankBase):
    pass


class Tank(TankBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ Batch Schemas ============
class BatchBase(BaseModel):
    tank_id: int
    cultivar: Optional[str] = None
    avg_weight: Optional[float] = None
    firmness: Optional[float] = None
    leaf_thickness: Optional[float] = None
    total_quantity: Optional[float] = None
    room_temp: Optional[float] = None
    season: Optional[str] = None
    initial_salinity: Optional[float] = None
    initial_water_temp: Optional[float] = None


class BatchCreate(BatchBase):
    pass


class BatchFinish(BaseModel):
    final_cabbage_salinity: Optional[float] = None
    bend_test: Optional[float] = None
    output_quantity: Optional[float] = None
    quality_grade: Optional[str] = None
    notes: Optional[str] = None
    # 세척 데이터
    wash1_top_salinity: Optional[float] = None
    wash1_bottom_salinity: Optional[float] = None
    wash1_water_temp: Optional[float] = None
    wash2_top_salinity: Optional[float] = None
    wash2_bottom_salinity: Optional[float] = None
    wash2_water_temp: Optional[float] = None
    wash3_top_salinity: Optional[float] = None
    wash3_bottom_salinity: Optional[float] = None
    wash3_water_temp: Optional[float] = None


class Batch(BatchBase):
    id: int
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    final_cabbage_salinity: Optional[float] = None
    bend_test: Optional[float] = None
    output_quantity: Optional[float] = None
    quality_grade: Optional[str] = None
    notes: Optional[str] = None
    wash1_top_salinity: Optional[float] = None
    wash1_bottom_salinity: Optional[float] = None
    wash1_water_temp: Optional[float] = None
    wash2_top_salinity: Optional[float] = None
    wash2_bottom_salinity: Optional[float] = None
    wash2_water_temp: Optional[float] = None
    wash3_top_salinity: Optional[float] = None
    wash3_bottom_salinity: Optional[float] = None
    wash3_water_temp: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ Measurement Schemas ============
class MeasurementBase(BaseModel):
    top_salinity: Optional[float] = None
    bottom_salinity: Optional[float] = None
    water_temp: Optional[float] = None
    ph: Optional[float] = None
    memo: Optional[str] = None


class MeasurementCreate(MeasurementBase):
    # 파생 변수 (선택적으로 직접 입력하거나 서버에서 계산)
    salinity_avg: Optional[float] = None
    salinity_diff: Optional[float] = None
    osmotic_pressure_index: Optional[float] = None
    accumulated_temp: Optional[float] = None


class Measurement(MeasurementBase):
    id: int
    batch_id: int
    timestamp: datetime
    salinity_avg: Optional[float] = None
    salinity_diff: Optional[float] = None
    osmotic_pressure_index: Optional[float] = None
    accumulated_temp: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Response Schemas ============
class BatchWithMeasurements(Batch):
    measurements: list[Measurement] = []


class ActiveBatchResponse(BaseModel):
    tank_id: int
    batch: Optional[Batch] = None


class HealthResponse(BaseModel):
    status: str
    database: str
    timestamp: datetime
