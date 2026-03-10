-- 동촌에프에스 ML 모듈 초기 스키마
-- PostgreSQL 15+ with pgvector extension

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. 절임조 마스터 테이블
CREATE TABLE IF NOT EXISTS tanks (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    capacity DECIMAL(10,2),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 기본 절임조 3개 생성
INSERT INTO tanks (name, capacity) VALUES
    ('절임조 1', 1000),
    ('절임조 2', 1000),
    ('절임조 3', 1000)
ON CONFLICT DO NOTHING;

-- 2. 배치 정보 테이블
CREATE TABLE IF NOT EXISTS batches (
    id SERIAL PRIMARY KEY,
    tank_id INTEGER NOT NULL REFERENCES tanks(id),
    status VARCHAR(20) NOT NULL DEFAULT 'active', -- active, completed

    -- 시간 정보
    start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,

    -- 배추 특성 (입력)
    cultivar VARCHAR(50),           -- 품종 (해남/괴산/강원/기타)
    avg_weight DECIMAL(10,2),       -- 평균 무게 (kg)
    firmness DECIMAL(10,2),         -- 단단함 (센서값)
    leaf_thickness DECIMAL(10,2),   -- 잎 두께 (1-5)
    total_quantity DECIMAL(10,2),   -- 입고량 (kg)

    -- 환경 정보
    room_temp DECIMAL(5,2),         -- 실내온도 (°C)
    season VARCHAR(20),             -- 계절 (봄/여름/가을/겨울)
    initial_salinity DECIMAL(5,2),  -- 초기 염도 (%)
    initial_water_temp DECIMAL(5,2),-- 초기 물온도 (°C)

    -- 결과 (종료 시)
    final_cabbage_salinity DECIMAL(5,2), -- 최종 배추 염도 (%)
    bend_test DECIMAL(3,1),         -- 관능평가 - 휘어짐 (1-5)
    output_quantity DECIMAL(10,2),  -- 출하량 (kg)
    quality_grade VARCHAR(10),      -- 품질등급 (A/B/C 또는 상/중/하)
    notes TEXT,                     -- 비고

    -- 세척 데이터 (3회차)
    wash1_top_salinity DECIMAL(5,2),
    wash1_bottom_salinity DECIMAL(5,2),
    wash1_water_temp DECIMAL(5,2),
    wash2_top_salinity DECIMAL(5,2),
    wash2_bottom_salinity DECIMAL(5,2),
    wash2_water_temp DECIMAL(5,2),
    wash3_top_salinity DECIMAL(5,2),
    wash3_bottom_salinity DECIMAL(5,2),
    wash3_water_temp DECIMAL(5,2),

    -- 메타
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. 측정 기록 테이블
CREATE TABLE IF NOT EXISTS measurements (
    id SERIAL PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- 센서 데이터
    top_salinity DECIMAL(5,2),      -- 상단 염도
    bottom_salinity DECIMAL(5,2),   -- 하단 염도
    water_temp DECIMAL(5,2),        -- 수온
    ph DECIMAL(4,2),                -- pH 값
    memo TEXT,                      -- 메모

    -- 파생 변수
    salinity_avg DECIMAL(5,2),      -- 평균 염도
    salinity_diff DECIMAL(5,2),     -- 염도 차이 (상-하)
    osmotic_pressure_index DECIMAL(10,4), -- 삼투압 지수
    accumulated_temp DECIMAL(10,2), -- 적산 온도

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. ML 모델 메타데이터 테이블
CREATE TABLE IF NOT EXISTS ml_models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    version VARCHAR(20) NOT NULL,
    model_type VARCHAR(50) NOT NULL, -- optimizer, time_predictor, quality_classifier
    s3_path VARCHAR(500),
    metrics JSONB,                  -- {accuracy, rmse, f1_score, etc.}
    is_active BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. ML 예측 로그 테이블
CREATE TABLE IF NOT EXISTS prediction_logs (
    id SERIAL PRIMARY KEY,
    batch_id INTEGER REFERENCES batches(id) ON DELETE SET NULL,
    model_type VARCHAR(50) NOT NULL,
    model_version VARCHAR(20),
    input_data JSONB NOT NULL,
    prediction JSONB NOT NULL,
    confidence DECIMAL(5,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. AI 인사이트 로그 테이블
CREATE TABLE IF NOT EXISTS insight_logs (
    id SERIAL PRIMARY KEY,
    batch_id INTEGER REFERENCES batches(id) ON DELETE SET NULL,
    prediction_log_id INTEGER REFERENCES prediction_logs(id) ON DELETE SET NULL,
    prompt TEXT,
    response TEXT,
    tokens_used INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_batches_tank_id ON batches(tank_id);
CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status);
CREATE INDEX IF NOT EXISTS idx_batches_start_time ON batches(start_time);
CREATE INDEX IF NOT EXISTS idx_measurements_batch_id ON measurements(batch_id);
CREATE INDEX IF NOT EXISTS idx_measurements_timestamp ON measurements(timestamp);
CREATE INDEX IF NOT EXISTS idx_prediction_logs_batch_id ON prediction_logs(batch_id);
CREATE INDEX IF NOT EXISTS idx_prediction_logs_model_type ON prediction_logs(model_type);

-- updated_at 자동 업데이트 함수
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 트리거 적용
DROP TRIGGER IF EXISTS update_tanks_updated_at ON tanks;
CREATE TRIGGER update_tanks_updated_at
    BEFORE UPDATE ON tanks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_batches_updated_at ON batches;
CREATE TRIGGER update_batches_updated_at
    BEFORE UPDATE ON batches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
