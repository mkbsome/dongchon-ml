from sqlalchemy import Column, Integer, String, Numeric, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Tank(Base):
    __tablename__ = "tanks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    capacity = Column(Numeric(10, 2))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    batches = relationship("Batch", back_populates="tank")


class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, index=True)
    tank_id = Column(Integer, ForeignKey("tanks.id"), nullable=False)
    status = Column(String(20), nullable=False, default="active")

    # 시간 정보
    start_time = Column(DateTime, server_default=func.now())
    end_time = Column(DateTime)

    # 배추 특성
    cultivar = Column(String(50))
    avg_weight = Column(Numeric(10, 2))
    firmness = Column(Numeric(10, 2))
    leaf_thickness = Column(Numeric(10, 2))
    total_quantity = Column(Numeric(10, 2))

    # 환경 정보
    room_temp = Column(Numeric(5, 2))
    season = Column(String(20))
    initial_salinity = Column(Numeric(5, 2))
    initial_water_temp = Column(Numeric(5, 2))

    # 결과
    final_cabbage_salinity = Column(Numeric(5, 2))
    bend_test = Column(Numeric(3, 1))
    output_quantity = Column(Numeric(10, 2))
    quality_grade = Column(String(10))
    notes = Column(Text)

    # 세척 데이터
    wash1_top_salinity = Column(Numeric(5, 2))
    wash1_bottom_salinity = Column(Numeric(5, 2))
    wash1_water_temp = Column(Numeric(5, 2))
    wash2_top_salinity = Column(Numeric(5, 2))
    wash2_bottom_salinity = Column(Numeric(5, 2))
    wash2_water_temp = Column(Numeric(5, 2))
    wash3_top_salinity = Column(Numeric(5, 2))
    wash3_bottom_salinity = Column(Numeric(5, 2))
    wash3_water_temp = Column(Numeric(5, 2))

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    tank = relationship("Tank", back_populates="batches")
    measurements = relationship("Measurement", back_populates="batch", cascade="all, delete-orphan")
    prediction_logs = relationship("PredictionLog", back_populates="batch")
    insight_logs = relationship("InsightLog", back_populates="batch")


class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, server_default=func.now())

    # 센서 데이터
    top_salinity = Column(Numeric(5, 2))
    bottom_salinity = Column(Numeric(5, 2))
    water_temp = Column(Numeric(5, 2))
    ph = Column(Numeric(4, 2))
    memo = Column(Text)

    # 파생 변수
    salinity_avg = Column(Numeric(5, 2))
    salinity_diff = Column(Numeric(5, 2))
    osmotic_pressure_index = Column(Numeric(10, 4))
    accumulated_temp = Column(Numeric(10, 2))

    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    batch = relationship("Batch", back_populates="measurements")


class MLModel(Base):
    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    version = Column(String(20), nullable=False)
    model_type = Column(String(50), nullable=False)
    s3_path = Column(String(500))
    metrics = Column(JSON)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class PredictionLog(Base):
    __tablename__ = "prediction_logs"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="SET NULL"))
    model_type = Column(String(50), nullable=False)
    model_version = Column(String(20))
    input_data = Column(JSON, nullable=False)
    prediction = Column(JSON, nullable=False)
    confidence = Column(Numeric(5, 4))
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    batch = relationship("Batch", back_populates="prediction_logs")
    insight_logs = relationship("InsightLog", back_populates="prediction_log")


class InsightLog(Base):
    __tablename__ = "insight_logs"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="SET NULL"))
    prediction_log_id = Column(Integer, ForeignKey("prediction_logs.id", ondelete="SET NULL"))
    prompt = Column(Text)
    response = Column(Text)
    tokens_used = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    batch = relationship("Batch", back_populates="insight_logs")
    prediction_log = relationship("PredictionLog", back_populates="insight_logs")
