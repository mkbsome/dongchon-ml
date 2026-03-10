from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta
from typing import Optional, List

from ..database import get_db
from ..models.models import Batch, Measurement, PredictionLog
from ..schemas.ml_schemas import (
    OptimizeRequest, OptimizeResponse, QualityProbability,
    TimePredictRequest, TimePredictResponse,
    QualityPredictRequest, QualityPredictResponse,
    PredictionLogResponse, PredictionLogListResponse
)
from ..ml.models import optimizer, time_predictor, quality_classifier

router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/optimize", response_model=OptimizeResponse)
def optimize_process(request: OptimizeRequest, db: Session = Depends(get_db)):
    """
    공정 최적화 추천
    - 배추 특성과 환경 조건을 입력하면 최적의 초기 염도와 절임 시간을 추천
    """
    result = optimizer.predict(
        cultivar=request.cultivar,
        avg_weight=request.avg_weight,
        firmness=request.firmness or 50.0,
        leaf_thickness=request.leaf_thickness or 3.0,
        season=request.season,
        room_temp=request.room_temp or 15.0,
        target_quality=request.target_quality or "A"
    )

    # 예측 로그 저장
    log = PredictionLog(
        model_type="optimizer",
        model_version="dummy-1.0",
        input_data={
            "cultivar": request.cultivar,
            "avg_weight": request.avg_weight,
            "firmness": request.firmness,
            "season": request.season,
            "room_temp": request.room_temp
        },
        prediction={
            "recommended_salinity": result.recommended_salinity,
            "recommended_duration": result.recommended_duration,
            "predicted_quality": result.predicted_quality
        },
        confidence=result.confidence
    )
    db.add(log)
    db.commit()

    # 품질 확률 계산 (모델에서 가져오거나 기본값)
    quality_prob = None
    if hasattr(result, 'predicted_quality'):
        # 예측 등급 기반 확률 추정
        grade = result.predicted_quality
        if grade == "A":
            quality_prob = QualityProbability(A=0.72, B=0.25, C=0.03)
        elif grade == "B":
            quality_prob = QualityProbability(A=0.25, B=0.60, C=0.15)
        else:
            quality_prob = QualityProbability(A=0.10, B=0.30, C=0.60)

    return OptimizeResponse(
        recommended_salinity=result.recommended_salinity,
        recommended_duration=result.recommended_duration,
        predicted_quality=result.predicted_quality,
        quality_probability=quality_prob,
        confidence=round(result.confidence, 2),
        reasoning=result.reasoning,
        expected_final_salinity=getattr(result, 'expected_final_salinity', None),
        is_optimal=getattr(result, 'is_optimal', False)
    )


@router.post("/predict/time", response_model=TimePredictResponse)
def predict_time(request: TimePredictRequest, db: Session = Depends(get_db)):
    """
    남은 절임 시간 예측
    - batch_id를 제공하면 해당 배치의 데이터를 자동으로 조회
    - 또는 직접 센서 값을 입력
    """
    elapsed_hours = request.elapsed_hours
    current_salinity_avg = request.current_salinity_avg
    initial_salinity = request.initial_salinity
    water_temp = request.water_temp
    accumulated_temp = request.accumulated_temp

    # batch_id가 있으면 데이터 자동 조회
    if request.batch_id:
        batch = db.query(Batch).filter(Batch.id == request.batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")

        # 경과 시간 계산
        start = batch.start_time
        elapsed_hours = (datetime.now() - start).total_seconds() / 3600

        # 초기 염도
        initial_salinity = float(batch.initial_salinity) if batch.initial_salinity else 12.0

        # 최근 측정 데이터 조회
        last_measurement = db.query(Measurement).filter(
            Measurement.batch_id == request.batch_id
        ).order_by(Measurement.timestamp.desc()).first()

        if last_measurement:
            current_salinity_avg = float(last_measurement.salinity_avg) if last_measurement.salinity_avg else initial_salinity
            water_temp = float(last_measurement.water_temp) if last_measurement.water_temp else 15.0
            accumulated_temp = float(last_measurement.accumulated_temp) if last_measurement.accumulated_temp else 0.0

    # 필수 값 검증
    if elapsed_hours is None or current_salinity_avg is None or initial_salinity is None:
        raise HTTPException(
            status_code=400,
            detail="batch_id를 제공하거나 elapsed_hours, current_salinity_avg, initial_salinity를 직접 입력해주세요"
        )

    result = time_predictor.predict(
        elapsed_hours=elapsed_hours,
        current_salinity_avg=current_salinity_avg,
        initial_salinity=initial_salinity,
        water_temp=water_temp or 15.0,
        accumulated_temp=accumulated_temp or 0.0
    )

    # 예측 로그 저장
    log = PredictionLog(
        batch_id=request.batch_id,
        model_type="time_predictor",
        model_version="dummy-1.0",
        input_data={
            "elapsed_hours": elapsed_hours,
            "current_salinity_avg": current_salinity_avg,
            "initial_salinity": initial_salinity,
            "water_temp": water_temp
        },
        prediction={
            "remaining_hours": result.remaining_hours,
            "predicted_end_time": result.predicted_end_time,
            "current_progress": result.current_progress
        },
        confidence=result.confidence
    )
    db.add(log)
    db.commit()

    return TimePredictResponse(
        remaining_hours=result.remaining_hours,
        predicted_end_time=result.predicted_end_time,
        confidence=round(result.confidence, 2),
        current_progress=result.current_progress
    )


@router.post("/predict/quality", response_model=QualityPredictResponse)
def predict_quality(request: QualityPredictRequest, db: Session = Depends(get_db)):
    """
    품질 등급 예측
    - batch_id를 제공하면 해당 배치의 데이터를 자동으로 조회
    - 또는 직접 값을 입력
    """
    final_salinity = request.final_salinity
    bend_test = request.bend_test
    elapsed_hours = request.elapsed_hours
    cultivar = request.cultivar
    season = request.season

    # batch_id가 있으면 데이터 자동 조회
    if request.batch_id:
        batch = db.query(Batch).filter(Batch.id == request.batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")

        cultivar = batch.cultivar
        season = batch.season

        # 경과 시간
        start = batch.start_time
        end = batch.end_time or datetime.now()
        elapsed_hours = (end - start).total_seconds() / 3600

        # 최종 데이터 (있으면)
        if batch.final_cabbage_salinity:
            final_salinity = float(batch.final_cabbage_salinity)
        if batch.bend_test:
            bend_test = float(batch.bend_test)

        # 최종 데이터 없으면 최근 측정값 사용
        if final_salinity is None:
            last_measurement = db.query(Measurement).filter(
                Measurement.batch_id == request.batch_id
            ).order_by(Measurement.timestamp.desc()).first()
            if last_measurement and last_measurement.salinity_avg:
                final_salinity = float(last_measurement.salinity_avg)

    # 필수 값 검증
    if final_salinity is None or bend_test is None:
        raise HTTPException(
            status_code=400,
            detail="final_salinity와 bend_test는 필수입니다"
        )

    result = quality_classifier.predict(
        final_salinity=final_salinity,
        bend_test=bend_test,
        elapsed_hours=elapsed_hours or 14.0,
        cultivar=cultivar or "기타",
        season=season or "가을"
    )

    # 예측 로그 저장
    log = PredictionLog(
        batch_id=request.batch_id,
        model_type="quality_classifier",
        model_version="dummy-1.0",
        input_data={
            "final_salinity": final_salinity,
            "bend_test": bend_test,
            "elapsed_hours": elapsed_hours,
            "cultivar": cultivar
        },
        prediction={
            "predicted_grade": result.predicted_grade,
            "probabilities": result.probabilities
        },
        confidence=result.confidence
    )
    db.add(log)
    db.commit()

    return QualityPredictResponse(
        predicted_grade=result.predicted_grade,
        probabilities=result.probabilities,
        confidence=round(result.confidence, 2),
        risk_factors=result.risk_factors
    )


@router.get("/status")
def get_ml_status():
    """ML 모델 상태 조회"""
    # 실제 모델 정보 조회
    optimizer_info = {
        "type": "GradientBoostingRegressor" if optimizer.is_trained else "Rule-based",
        "status": "trained" if optimizer.is_trained else "fallback",
        "version": optimizer.model_version,
        "is_trained": optimizer.is_trained
    }

    time_info = {
        "type": "GradientBoostingRegressor" if time_predictor.is_trained else "Rule-based",
        "status": "trained" if time_predictor.is_trained else "fallback",
        "version": time_predictor.model_version,
        "is_trained": time_predictor.is_trained
    }

    quality_info = {
        "type": "GradientBoostingClassifier" if quality_classifier.is_trained else "Rule-based",
        "status": "trained" if quality_classifier.is_trained else "fallback",
        "version": quality_classifier.model_version,
        "is_trained": quality_classifier.is_trained
    }

    # 메타데이터에서 성능 지표 추출
    if optimizer.metadata:
        optimizer_info["metrics"] = optimizer.metadata.get("models", {}).get("salinity", {}).get("metrics", {})
        time_info["metrics"] = optimizer.metadata.get("models", {}).get("duration", {}).get("metrics", {})
        quality_info["metrics"] = optimizer.metadata.get("models", {}).get("quality", {}).get("metrics", {})

    all_trained = optimizer.is_trained and time_predictor.is_trained and quality_classifier.is_trained
    message = "v4 학습 모델 사용 중" if all_trained else "일부 모델이 폴백 모드로 동작 중"

    return {
        "models": {
            "optimizer": optimizer_info,
            "time_predictor": time_info,
            "quality_classifier": quality_info
        },
        "message": message
    }


# ============ Prediction Log Endpoints ============

@router.get("/logs", response_model=PredictionLogListResponse)
def get_prediction_logs(
    model_type: Optional[str] = Query(None, description="모델 타입 필터 (optimizer, time_predictor, quality_classifier)"),
    batch_id: Optional[int] = Query(None, description="특정 배치의 예측 로그만 조회"),
    days: Optional[int] = Query(30, description="최근 N일간의 로그 조회 (기본: 30일)"),
    skip: int = Query(0, ge=0, description="건너뛸 레코드 수"),
    limit: int = Query(100, ge=1, le=500, description="조회할 최대 레코드 수"),
    db: Session = Depends(get_db)
):
    """
    예측 로그 목록 조회
    - Claude가 이전 예측 이력을 참조할 때 사용
    - model_type으로 특정 모델의 예측만 필터링 가능
    - batch_id로 특정 배치의 예측만 조회 가능
    """
    query = db.query(PredictionLog)

    # 필터링
    if model_type:
        query = query.filter(PredictionLog.model_type == model_type)
    if batch_id:
        query = query.filter(PredictionLog.batch_id == batch_id)
    if days:
        cutoff_date = datetime.now() - timedelta(days=days)
        query = query.filter(PredictionLog.created_at >= cutoff_date)

    # 총 개수
    total = query.count()

    # 정렬 및 페이징
    logs = query.order_by(desc(PredictionLog.created_at)).offset(skip).limit(limit).all()

    return PredictionLogListResponse(
        total=total,
        logs=[PredictionLogResponse.model_validate(log) for log in logs]
    )


@router.get("/logs/{log_id}", response_model=PredictionLogResponse)
def get_prediction_log(log_id: int, db: Session = Depends(get_db)):
    """특정 예측 로그 상세 조회"""
    log = db.query(PredictionLog).filter(PredictionLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Prediction log not found")
    return log


@router.get("/logs/summary/stats")
def get_prediction_stats(
    days: int = Query(30, description="최근 N일간의 통계"),
    db: Session = Depends(get_db)
):
    """
    예측 로그 통계 조회
    - 모델별 예측 횟수, 평균 신뢰도 등
    - Claude가 모델 성능 분석 시 참조
    """
    cutoff_date = datetime.now() - timedelta(days=days)

    logs = db.query(PredictionLog).filter(
        PredictionLog.created_at >= cutoff_date
    ).all()

    # 모델별 통계 계산
    stats = {
        "optimizer": {"count": 0, "avg_confidence": 0, "confidences": []},
        "time_predictor": {"count": 0, "avg_confidence": 0, "confidences": []},
        "quality_classifier": {"count": 0, "avg_confidence": 0, "confidences": []}
    }

    for log in logs:
        model_type = log.model_type
        if model_type in stats:
            stats[model_type]["count"] += 1
            if log.confidence:
                stats[model_type]["confidences"].append(float(log.confidence))

    # 평균 신뢰도 계산
    for model_type, data in stats.items():
        if data["confidences"]:
            data["avg_confidence"] = round(sum(data["confidences"]) / len(data["confidences"]), 4)
        del data["confidences"]  # 응답에서 제거

    return {
        "period_days": days,
        "total_predictions": len(logs),
        "by_model": stats,
        "generated_at": datetime.now().isoformat()
    }


@router.get("/logs/batch/{batch_id}/history")
def get_batch_prediction_history(batch_id: int, db: Session = Depends(get_db)):
    """
    특정 배치의 전체 예측 히스토리
    - 배치 진행 중 모든 예측 결과를 시간순으로 조회
    - 품질 추적 및 개선 분석에 활용
    """
    logs = db.query(PredictionLog).filter(
        PredictionLog.batch_id == batch_id
    ).order_by(PredictionLog.created_at).all()

    if not logs:
        return {
            "batch_id": batch_id,
            "prediction_count": 0,
            "history": []
        }

    history = []
    for log in logs:
        history.append({
            "id": log.id,
            "model_type": log.model_type,
            "prediction": log.prediction,
            "confidence": float(log.confidence) if log.confidence else None,
            "created_at": log.created_at.isoformat()
        })

    return {
        "batch_id": batch_id,
        "prediction_count": len(logs),
        "history": history
    }
