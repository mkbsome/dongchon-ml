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
    PredictionLogResponse, PredictionLogListResponse,
    CompletionDecisionRequest, CompletionDecisionResponse, CompletionScenario
)
from ..ml.models import optimizer, time_predictor, quality_classifier, calculate_corrected_duration

router = APIRouter(prefix="/ml", tags=["ml"])


def convert_ui_firmness(ui_firmness: float) -> float:
    """UI firmness (0-100) → 학습 데이터 firmness (5-22)"""
    # UI 0 → 5, UI 100 → 22
    return 5.0 + (ui_firmness / 100.0) * 17.0


def convert_ui_leaf_thickness(ui_thickness: float) -> int:
    """UI leaf_thickness (0.2-1.0 mm) → 학습 데이터 (1-5 mm)"""
    # UI가 이미 mm 단위면 그대로, 아니면 스케일 조정
    if ui_thickness < 1.5:
        # 슬라이더가 0.2-1.0 범위인 경우 → 1-5로 스케일
        return max(1, min(5, int(ui_thickness * 5)))
    else:
        # 이미 올바른 범위
        return max(1, min(5, int(ui_thickness)))


# 품종명 매핑 (프론트엔드 한글 → 학습 데이터 품종)
CULTIVAR_MAP = {
    '해남': '불암플러스',
    '괴산': '불암3호',
    '강원': '청명',
    '충북': '휘파람골드',
    '불암3호': '불암3호',
    '불암플러스': '불암플러스',
    '청명': '청명',
    '휘파람골드': '휘파람골드',
}


@router.post("/optimize", response_model=OptimizeResponse)
def optimize_process(request: OptimizeRequest, db: Session = Depends(get_db)):
    """
    공정 최적화 추천
    - 배추 특성과 환경 조건을 입력하면 최적의 초기 염도와 절임 시간을 추천
    """
    # 피처 변환
    firmness = convert_ui_firmness(request.firmness or 50.0)
    leaf_thickness = convert_ui_leaf_thickness(request.leaf_thickness or 3.0)
    cultivar = CULTIVAR_MAP.get(request.cultivar, request.cultivar)

    result = optimizer.predict(
        cultivar=cultivar,
        avg_weight=request.avg_weight,
        firmness=firmness,
        leaf_thickness=leaf_thickness,
        season=request.season,
        room_temp=request.room_temp or 18.0,
        target_quality=request.target_quality or "A",
        water_temp=request.water_temp  # 계절별 기본값은 models.py에서 처리
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


@router.post("/completion-decision", response_model=CompletionDecisionResponse)
def get_completion_decision(request: CompletionDecisionRequest, db: Session = Depends(get_db)):
    """
    완료 시점 결정 - 여러 시나리오별 품질 예측
    - 현재 시점, +2h, +4h, +6h 시나리오 분석
    - 각 시점에서의 예상 품질 등급과 확률 제공
    - 최적의 완료 시점 추천
    """
    # 배치 조회
    batch = db.query(Batch).filter(Batch.id == request.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # 현재 상태 계산
    start = batch.start_time
    elapsed_hours = (datetime.now() - start).total_seconds() / 3600
    initial_salinity = float(batch.initial_salinity) if batch.initial_salinity else 12.0

    # 최근 측정 데이터 조회
    last_measurement = db.query(Measurement).filter(
        Measurement.batch_id == request.batch_id
    ).order_by(Measurement.timestamp.desc()).first()

    current_salinity = initial_salinity
    water_temp = 15.0
    accumulated_temp = 0.0
    bend_test = 75.0  # 기본값

    if last_measurement:
        current_salinity = float(last_measurement.salinity_avg) if last_measurement.salinity_avg else initial_salinity
        water_temp = float(last_measurement.water_temp) if last_measurement.water_temp else 15.0
        accumulated_temp = float(last_measurement.accumulated_temp) if last_measurement.accumulated_temp else 0.0

    # 염도 변화율 추정
    if elapsed_hours > 0:
        salinity_drop_rate = (initial_salinity - current_salinity) / elapsed_hours
    else:
        salinity_drop_rate = 0.5  # 기본 변화율

    # 현재 상태
    current_status = {
        "elapsed_hours": round(elapsed_hours, 1),
        "current_salinity": round(current_salinity, 2),
        "initial_salinity": initial_salinity,
        "water_temp": water_temp,
        "cultivar": batch.cultivar,
        "season": batch.season
    }

    # 시나리오 생성 (0h, +2h, +4h, +6h)
    scenarios = []
    scenario_hours = [0, 2, 4, 6]
    best_a_prob = 0
    best_index = 0

    for i, add_hours in enumerate(scenario_hours):
        # 예상 시점의 총 경과 시간
        total_hours = elapsed_hours + add_hours

        # 예상 염도 (선형 감소 추정)
        predicted_salinity = max(1.5, current_salinity - salinity_drop_rate * add_hours)

        # 휘어짐 점수 추정 (시간이 지날수록 좋아짐, 최대 90)
        predicted_bend = min(90, bend_test + add_hours * 2)

        # 품질 예측
        quality_result = quality_classifier.predict(
            final_salinity=predicted_salinity,
            bend_test=predicted_bend,
            elapsed_hours=total_hours,
            cultivar=batch.cultivar or "기타",
            season=batch.season or "가을"
        )

        a_prob = quality_result.probabilities.get('A', 0)
        is_best = a_prob > best_a_prob
        if is_best:
            best_a_prob = a_prob
            best_index = i

        scenario = CompletionScenario(
            hours_from_now=add_hours,
            predicted_salinity=round(predicted_salinity, 2),
            predicted_grade=quality_result.predicted_grade,
            grade_probabilities=quality_result.probabilities,
            confidence=quality_result.confidence,
            is_recommended=False  # 나중에 설정
        )
        scenarios.append(scenario)

    # 최적 시나리오 표시
    scenarios[best_index].is_recommended = True

    # 추천 메시지 생성
    if best_index == 0:
        recommendation = "현재 시점에서 완료하는 것이 가장 좋습니다. A등급 확률이 가장 높습니다."
    elif best_index == 1:
        recommendation = f"2시간 후 완료를 추천합니다. A등급 확률 {best_a_prob:.0%}로 최적의 결과가 예상됩니다."
    elif best_index == 2:
        recommendation = f"4시간 후 완료를 추천합니다. 현재보다 A등급 확률이 {best_a_prob:.0%}로 높아집니다."
    else:
        recommendation = f"6시간 이상 추가 절임이 필요합니다. 예상 A등급 확률: {best_a_prob:.0%}"

    # 예측 로그 저장
    log = PredictionLog(
        batch_id=request.batch_id,
        model_type="completion_decision",
        model_version="v1",
        input_data=current_status,
        prediction={
            "optimal_scenario_index": best_index,
            "optimal_add_hours": scenario_hours[best_index],
            "best_a_probability": best_a_prob
        },
        confidence=scenarios[best_index].confidence
    )
    db.add(log)
    db.commit()

    return CompletionDecisionResponse(
        batch_id=request.batch_id,
        current_status=current_status,
        scenarios=scenarios,
        recommendation=recommendation,
        optimal_scenario_index=best_index,
        generated_at=datetime.now().isoformat()
    )


@router.post("/recalculate-duration")
def recalculate_duration(
    salinity: float = Query(..., description="조정된 초기 염도 (%)"),
    season: str = Query(..., description="계절"),
    water_temp: float = Query(None, description="염수 온도 (°C)"),
    avg_weight: float = Query(3.0, description="배추 평균 무게 (kg)"),
    base_duration: float = Query(None, description="기존 예측 시간 (없으면 계절 기본값)")
):
    """
    염도 조정에 따른 절임 시간 재계산

    사용자가 슬라이더로 염도를 조정하면 이 API를 호출하여
    상호 연관된 절임 시간을 동적으로 업데이트합니다.
    """
    # 수온 기본값
    if water_temp is None:
        water_temp_defaults = {'봄': 14, '여름': 22, '가을': 16, '겨울': 10}
        water_temp = water_temp_defaults.get(season, 15)

    # 기본 시간 (수온 기반 - 계절이 아닌 온도가 핵심)
    if base_duration is None:
        if water_temp <= 10:
            base_duration = 46.0  # 저온: 이틀절임 수준
        elif water_temp >= 22:
            base_duration = 22.0  # 고온: 하루절임 수준
        else:
            # 10°C ~ 22°C 사이 선형 보간
            base_duration = 46.0 - (water_temp - 10) * (46.0 - 22.0) / (22 - 10)

    # 후처리 보정 적용
    corrected_duration = calculate_corrected_duration(
        base_duration=base_duration,
        salinity=salinity,
        water_temp=water_temp,
        season=season,
        avg_weight=avg_weight
    )

    # 기본 염도 대비 변화 설명
    season_base_salinity = {
        '겨울': 10.5,
        '여름': 13.0,
        '봄': 12.0,
        '가을': 12.0
    }
    base_salinity = season_base_salinity.get(season, 12.0)
    salinity_diff = salinity - base_salinity

    if salinity_diff > 0.5:
        direction = "높은 염도로 인해 절임 시간 단축"
    elif salinity_diff < -0.5:
        direction = "낮은 염도로 인해 절임 시간 증가"
    else:
        direction = "계절 기준 적정 범위 내"

    return {
        "adjusted_salinity": round(salinity, 1),
        "recalculated_duration": corrected_duration,
        "base_duration": base_duration,
        "duration_change": round(corrected_duration - base_duration, 1),
        "direction": direction,
        "water_temp": water_temp,
        "season": season
    }


@router.get("/status")
def get_ml_status():
    """ML 모델 상태 조회 (v2 메타데이터 연동)"""
    # 메타데이터에서 성능 지표 가져오기
    opt_meta = optimizer.metadata.get('metrics', {})
    time_meta = time_predictor.metadata.get('metrics', {})
    qual_meta = quality_classifier.metadata.get('metrics', {})

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

    # v2 메타데이터에서 성능 지표 로드
    if optimizer.is_trained and opt_meta:
        duration_m = opt_meta.get('optimizer_duration', {})
        salinity_m = opt_meta.get('optimizer_salinity', {})
        optimizer_info["metrics"] = {
            "duration_mae": round(duration_m.get('mae', 0), 3),
            "duration_r2": round(duration_m.get('r2', 0), 3),
            "salinity_mae": round(salinity_m.get('mae', 0), 3),
            "salinity_r2": round(salinity_m.get('r2', 0), 3),
            "duration_features": duration_m.get('features', []),
        }
    if time_predictor.is_trained and time_meta:
        tp_m = time_meta.get('time_predictor', {})
        time_info["metrics"] = {
            "mae": round(tp_m.get('mae', 0), 3),
            "r2": round(tp_m.get('r2', 0), 3),
            "features": tp_m.get('features', []),
        }
    if quality_classifier.is_trained and qual_meta:
        qc_m = qual_meta.get('quality_classifier', {})
        quality_info["metrics"] = {
            "accuracy": round(qc_m.get('accuracy', 0), 3),
            "f1_weighted": round(qc_m.get('f1_weighted', 0), 3),
            "features": qc_m.get('features', []),
        }

    all_trained = optimizer.is_trained and time_predictor.is_trained and quality_classifier.is_trained
    version = optimizer.model_version if optimizer.is_trained else "fallback"
    message = f"{version} 학습 모델 사용 중" if all_trained else "일부 모델이 폴백 모드로 동작 중"

    # v2 변경사항 추가
    changes = optimizer.metadata.get('changes', [])

    return {
        "models": {
            "optimizer": optimizer_info,
            "time_predictor": time_info,
            "quality_classifier": quality_info
        },
        "message": message,
        "version": version,
        "changes": changes
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
