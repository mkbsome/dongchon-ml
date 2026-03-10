from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import get_settings

settings = get_settings()

# SQLite용 설정
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# Sync engine
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
)

# SQLite Foreign Key 활성화
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for getting DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables and seed data"""
    from .models.models import Tank  # Import models to register them
    Base.metadata.create_all(bind=engine)

    # Seed initial tank data
    db = SessionLocal()
    try:
        existing = db.query(Tank).count()
        if existing == 0:
            # 절임조 1, 2, 3 생성
            for i in range(1, 4):
                tank = Tank(id=i, name=f"절임조 {i}호", capacity=500, is_active=True)
                db.add(tank)
            db.commit()
            print("Initial tanks created: 절임조 1호, 2호, 3호")
    except Exception as e:
        print(f"Error seeding tanks: {e}")
        db.rollback()
    finally:
        db.close()
