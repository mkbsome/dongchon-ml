from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
import httpx

from ..database import get_db
from ..models.models import Batch, Measurement, InsightLog
from ..schemas.ml_schemas import InsightRequest, InsightResponse
from ..ml.models import optimizer, time_predictor, quality_classifier
from ..config import get_settings

router = APIRouter(prefix="/insight", tags=["insight"])

settings = get_settings()


# Claude 인사이트 요청 스키마
class OptimizationInsightRequest(BaseModel):
    """최적화 결과 기반 인사이트 요청"""
    optimization_result: dict
    input: dict


class ChatRequest(BaseModel):
    """Claude 채팅 요청"""
    message: str
    context: Optional[dict] = None


def generate_summary(
    batch: Batch,
    optimization_result: Optional[dict],
    time_result: Optional[dict],
    quality_result: Optional[dict]
) -> str:
    """종합 요약 생성 (더미 - 나중에 Claude API 연동)"""
    parts = []

    # 기본 정보
    elapsed = (datetime.now() - batch.start_time).total_seconds() / 3600
    parts.append(f"절임조 {batch.tank_id}번의 {batch.cultivar} 배추 배치입니다.")
    parts.append(f"현재 {elapsed:.1f}시간 경과했습니다.")

    # 시간 예측 정보
    if time_result:
        remaining = time_result.get("remaining_hours", 0)
        progress = time_result.get("current_progress", 0)
        parts.append(f"진행률 {progress:.0f}%, 약 {remaining:.1f}시간 후 완료 예상입니다.")

    # 품질 예측 정보
    if quality_result:
        grade = quality_result.get("predicted_grade", "?")
        confidence = quality_result.get("confidence", 0) * 100
        parts.append(f"현재 상태로는 {grade}등급이 예상됩니다 (신뢰도 {confidence:.0f}%).")

        # 위험 요소
        risks = quality_result.get("risk_factors", [])
        if risks:
            parts.append(f"주의사항: {', '.join(risks)}")

    return " ".join(parts)


def generate_recommendations(
    batch: Batch,
    optimization_result: Optional[dict],
    time_result: Optional[dict],
    quality_result: Optional[dict]
) -> list:
    """권장 사항 생성"""
    recommendations = []

    # 품질 위험 요소 기반 권장사항
    if quality_result:
        risks = quality_result.get("risk_factors", [])
        grade = quality_result.get("predicted_grade", "A")

        if "휘어짐 점수 낮음" in str(risks) or grade == "C":
            recommendations.append("휘어짐 점수가 낮습니다. 절임 시간을 조금 더 늘려보세요.")

        if "염도 부족" in str(risks):
            recommendations.append("염도가 목표치보다 낮습니다. 소금물 농도를 확인해주세요.")

        if "과염 위험" in str(risks):
            recommendations.append("염도가 높습니다. 세척 시 충분히 헹궈주세요.")

        if "과절임 위험" in str(risks):
            recommendations.append("절임 시간이 길어지고 있습니다. 상태를 확인해주세요.")

    # 시간 기반 권장사항
    if time_result:
        remaining = time_result.get("remaining_hours", 0)
        if remaining < 2:
            recommendations.append("완료가 임박했습니다. 품질 확인 준비를 해주세요.")
        elif remaining > 10:
            recommendations.append("아직 시간이 많이 남았습니다. 주기적으로 상태를 모니터링해주세요.")

    # 기본 권장사항
    if not recommendations:
        recommendations.append("현재 정상적으로 진행 중입니다. 계속 모니터링해주세요.")

    return recommendations


@router.post("/", response_model=InsightResponse)
async def get_insight(request: InsightRequest, db: Session = Depends(get_db)):
    """
    AI 인사이트 생성
    - 배치 정보를 기반으로 종합 분석 및 권장사항 제공
    - 추후 Claude API 연동하여 자연어 인사이트 생성
    """
    # 배치 조회
    batch = db.query(Batch).filter(Batch.id == request.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # 최근 측정 데이터
    last_measurement = db.query(Measurement).filter(
        Measurement.batch_id == request.batch_id
    ).order_by(Measurement.timestamp.desc()).first()

    optimization_result = None
    time_result = None
    quality_result = None

    # 1. 최적화 결과 (요청 시)
    if request.include_optimization:
        opt = optimizer.predict(
            cultivar=batch.cultivar,
            avg_weight=float(batch.avg_weight) if batch.avg_weight else 3.0,
            firmness=float(batch.firmness) if batch.firmness else 50.0,
            leaf_thickness=float(batch.leaf_thickness) if batch.leaf_thickness else 3.0,
            season=batch.season or "가을",
            room_temp=float(batch.room_temp) if batch.room_temp else 15.0
        )
        optimization_result = {
            "recommended_salinity": opt.recommended_salinity,
            "recommended_duration": opt.recommended_duration,
            "predicted_quality": opt.predicted_quality,
            "confidence": round(opt.confidence, 2),
            "reasoning": opt.reasoning
        }

    # 2. 시간 예측 (요청 시)
    if request.include_time_prediction and last_measurement:
        elapsed = (datetime.now() - batch.start_time).total_seconds() / 3600
        current_salinity = float(last_measurement.salinity_avg) if last_measurement.salinity_avg else 10.0
        initial_salinity = float(batch.initial_salinity) if batch.initial_salinity else 12.0

        time_pred = time_predictor.predict(
            elapsed_hours=elapsed,
            current_salinity_avg=current_salinity,
            initial_salinity=initial_salinity,
            water_temp=float(last_measurement.water_temp) if last_measurement.water_temp else 15.0,
            accumulated_temp=float(last_measurement.accumulated_temp) if last_measurement.accumulated_temp else 0.0
        )
        time_result = {
            "remaining_hours": time_pred.remaining_hours,
            "predicted_end_time": time_pred.predicted_end_time,
            "confidence": round(time_pred.confidence, 2),
            "current_progress": time_pred.current_progress
        }

    # 3. 품질 예측 (요청 시)
    if request.include_quality_prediction and last_measurement:
        elapsed = (datetime.now() - batch.start_time).total_seconds() / 3600
        final_salinity = float(batch.final_cabbage_salinity) if batch.final_cabbage_salinity else (
            float(last_measurement.salinity_avg) if last_measurement.salinity_avg else 2.5
        )
        bend_test = float(batch.bend_test) if batch.bend_test else 3.5  # 기본값

        quality_pred = quality_classifier.predict(
            final_salinity=final_salinity,
            bend_test=bend_test,
            elapsed_hours=elapsed,
            cultivar=batch.cultivar or "기타",
            season=batch.season or "가을"
        )
        quality_result = {
            "predicted_grade": quality_pred.predicted_grade,
            "probabilities": quality_pred.probabilities,
            "confidence": round(quality_pred.confidence, 2),
            "risk_factors": quality_pred.risk_factors
        }

    # 종합 요약 및 권장사항 생성
    summary = generate_summary(batch, optimization_result, time_result, quality_result)
    recommendations = generate_recommendations(batch, optimization_result, time_result, quality_result)

    # 인사이트 로그 저장
    insight_log = InsightLog(
        batch_id=request.batch_id,
        prompt=f"Batch {request.batch_id} insight request",
        response=summary,
    )
    db.add(insight_log)
    db.commit()

    return InsightResponse(
        batch_id=request.batch_id,
        summary=summary,
        optimization=optimization_result,
        time_prediction=time_result,
        quality_prediction=quality_result,
        recommendations=recommendations,
        generated_at=datetime.now().isoformat()
    )


@router.get("/batch/{batch_id}")
async def get_quick_insight(batch_id: int, db: Session = Depends(get_db)):
    """
    간단한 인사이트 조회 (GET 방식)
    """
    request = InsightRequest(
        batch_id=batch_id,
        include_optimization=True,
        include_time_prediction=True,
        include_quality_prediction=True
    )
    return await get_insight(request, db)


@router.post("/claude")
async def get_claude_insight(request: InsightRequest, db: Session = Depends(get_db)):
    """
    Claude API를 통한 자연어 인사이트 생성
    - 현재는 플레이스홀더 (API 키 설정 후 활성화)
    """
    if not settings.claude_api_key:
        raise HTTPException(
            status_code=503,
            detail="Claude API가 설정되지 않았습니다. .env 파일에 CLAUDE_API_KEY를 설정해주세요."
        )

    # TODO: Claude API 연동 구현
    # 1. ML 예측 결과 수집
    # 2. 프롬프트 구성
    # 3. Claude API 호출
    # 4. 응답 파싱 및 반환

    return {
        "status": "not_implemented",
        "message": "Claude API 연동은 추후 구현 예정입니다."
    }


def generate_optimization_insight(input_data: dict, result: dict) -> str:
    """최적화 결과 기반 인사이트 생성 (템플릿)"""
    cultivar = input_data.get('cultivar', '배추')
    weight = input_data.get('avg_weight', 3.0)
    firmness = input_data.get('firmness', 50)
    season = input_data.get('season', '가을')
    room_temp = input_data.get('room_temp', 18)

    salinity = result.get('recommended_salinity', 12.0)
    duration = result.get('recommended_duration', 22.0)
    quality = result.get('predicted_quality', 'A')
    final_salinity = result.get('expected_final_salinity', 1.8)
    is_optimal = result.get('is_optimal', True)

    hours = int(duration)
    minutes = int((duration - hours) * 60)

    # 인사이트 생성
    insight_parts = []

    # 1. 원물 분석
    firmness_desc = '높은' if firmness > 70 else '보통' if firmness > 40 else '낮은'
    insight_parts.append(f"현재 {cultivar} 배추({weight}kg)는 경도가 {firmness_desc} 편입니다.")

    # 2. 추천 결과
    time_str = f"{hours}시간" + (f" {minutes}분" if minutes > 0 else "")
    insight_parts.append(f"\n\n초기 염도 {salinity}%로 설정하시면 약 {time_str} 후 {quality}등급 품질을 기대할 수 있습니다.")

    # 3. 환경 조건 분석
    if room_temp > 22:
        insight_parts.append(f"\n\n현재 실내온도({room_temp}°C)가 다소 높으니 염도 침투가 빠를 수 있습니다. 중간 체크를 권장합니다.")
    elif room_temp < 15:
        insight_parts.append(f"\n\n현재 실내온도({room_temp}°C)가 다소 낮으니 염도 침투가 느릴 수 있습니다. 시간을 여유있게 잡으세요.")
    else:
        insight_parts.append(f"\n\n현재 실내온도({room_temp}°C)가 적정하여 염도 침투가 안정적으로 진행될 것입니다.")

    # 4. 계절별 조언
    if season == '겨울':
        insight_parts.append("\n\n겨울철에는 이틀절임을 권장합니다. 웃소금 사용을 고려해주세요.")
    elif season == '여름':
        insight_parts.append("\n\n여름철에는 수온이 높아 발효가 빠르니 상태를 자주 확인해주세요.")

    # 5. 최적 범위 경고
    if not is_optimal:
        insight_parts.append(f"\n\n⚠️ 예상 최종 염도({final_salinity}%)가 최적 범위(1.6~2.0%)를 벗어날 수 있습니다. 조건 조정을 권장합니다.")

    return "".join(insight_parts)


@router.post("/optimization")
async def get_optimization_insight(request: OptimizationInsightRequest):
    """
    최적화 결과 기반 인사이트 생성
    - Claude API 없이도 동작하는 템플릿 기반 인사이트
    - Claude API 설정 시 더 자연스러운 인사이트 생성
    """
    input_data = request.input
    result = request.optimization_result

    # Claude API가 설정되어 있으면 사용
    if settings.claude_api_key:
        try:
            insight = await call_claude_for_insight(input_data, result)
            return {"insight": insight}
        except Exception as e:
            print(f"Claude API 호출 실패, 템플릿 사용: {e}")

    # 템플릿 기반 인사이트 생성
    insight = generate_optimization_insight(input_data, result)
    return {"insight": insight}


async def call_claude_for_insight(input_data: dict, result: dict) -> str:
    """Claude API를 사용하여 인사이트 생성"""
    prompt = f"""당신은 김치 절임 공정 전문가입니다.
다음 ML 예측 결과를 바탕으로 현장 작업자에게 쉽게 이해할 수 있는 조언을 제공하세요.

[입력 조건]
- 품종: {input_data.get('cultivar', '배추')}
- 무게: {input_data.get('avg_weight', 3.0)}kg
- 경도: {input_data.get('firmness', 50)}/100
- 계절: {input_data.get('season', '가을')}
- 실내온도: {input_data.get('room_temp', 18)}°C

[예측 결과]
- 권장 초기 염도: {result.get('recommended_salinity', 12.0)}%
- 권장 절임 시간: {result.get('recommended_duration', 22.0)}시간
- 예상 최종 염도: {result.get('expected_final_salinity', 1.8)}%
- 예상 품질: {result.get('predicted_quality', 'A')}등급

주의사항:
1. 3~4문장으로 간결하게 작성
2. 실무적인 조언 포함
3. 위험 요소가 있다면 언급
4. 친근하고 이해하기 쉬운 말투 사용"""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.claude_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]


@router.post("/chat")
async def chat_with_claude(request: ChatRequest):
    """
    Claude와 대화형 질의응답
    """
    if not settings.claude_api_key:
        # API 키 없으면 기본 응답
        return {
            "response": "현재 AI 채팅 기능을 사용할 수 없습니다. 관리자에게 문의해주세요.",
            "tokens_used": 0
        }

    # 컨텍스트 구성
    system_prompt = """당신은 동촌에프에스의 AI 절임 어시스턴트입니다.

역할:
- 절임 공정에 대한 질문에 답변
- ML 예측 결과 해석 도움
- 문제 발생 시 해결책 제안

응답 원칙:
1. 짧고 명확하게 (3-4문장)
2. 실무 중심 조언
3. 불확실하면 솔직히 인정
4. 친근하고 이해하기 쉬운 말투"""

    context_info = ""
    if request.context:
        if request.context.get('optimization_result'):
            opt = request.context['optimization_result']
            context_info = f"""
현재 최적화 결과:
- 권장 염도: {opt.get('recommended_salinity')}%
- 권장 시간: {opt.get('recommended_duration')}시간
- 예상 품질: {opt.get('predicted_quality')}등급
"""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 500,
                    "system": system_prompt + context_info,
                    "messages": [{"role": "user", "content": request.message}]
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

            return {
                "response": data["content"][0]["text"],
                "tokens_used": data["usage"]["input_tokens"] + data["usage"]["output_tokens"]
            }

    except Exception as e:
        print(f"Claude API 호출 실패: {e}")
        return {
            "response": "죄송합니다. 현재 AI 응답을 생성할 수 없습니다. 잠시 후 다시 시도해주세요.",
            "tokens_used": 0
        }
