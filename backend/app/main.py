from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from .config import get_settings
from .database import engine, Base, init_db
from .api import batches, measurements, tanks, ml, insight

settings = get_settings()

# 앱 시작 시 테이블 자동 생성 (SQLite)
init_db()

# Create FastAPI app
app = FastAPI(
    title="동촌에프에스 ML API",
    description="배추 절임 공정 최적화를 위한 ML 모듈 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(tanks.router, prefix="/api")
app.include_router(batches.router, prefix="/api")
app.include_router(measurements.router, prefix="/api")
app.include_router(ml.router, prefix="/api")
app.include_router(insight.router, prefix="/api")


@app.get("/")
def root():
    """API 루트"""
    return {
        "name": "동촌에프에스 ML API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """헬스 체크"""
    db_status = "connected"
    try:
        from sqlalchemy import text
        from .database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }


# 개발 환경에서 직접 실행 시
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
