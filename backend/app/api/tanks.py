from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.models import Tank
from ..schemas.schemas import TankCreate, Tank as TankSchema

router = APIRouter(prefix="/tanks", tags=["tanks"])


@router.get("/", response_model=list[TankSchema])
def get_tanks(
    is_active: bool = None,
    db: Session = Depends(get_db)
):
    """모든 절임조 조회"""
    query = db.query(Tank)

    if is_active is not None:
        query = query.filter(Tank.is_active == is_active)

    return query.order_by(Tank.id).all()


@router.get("/{tank_id}", response_model=TankSchema)
def get_tank(tank_id: int, db: Session = Depends(get_db)):
    """절임조 단건 조회"""
    tank = db.query(Tank).filter(Tank.id == tank_id).first()
    if not tank:
        raise HTTPException(status_code=404, detail="Tank not found")
    return tank


@router.post("/", response_model=TankSchema)
def create_tank(tank_data: TankCreate, db: Session = Depends(get_db)):
    """절임조 생성"""
    new_tank = Tank(
        name=tank_data.name,
        capacity=tank_data.capacity,
        is_active=tank_data.is_active
    )

    db.add(new_tank)
    db.commit()
    db.refresh(new_tank)

    return new_tank


@router.put("/{tank_id}", response_model=TankSchema)
def update_tank(tank_id: int, tank_data: TankCreate, db: Session = Depends(get_db)):
    """절임조 수정"""
    tank = db.query(Tank).filter(Tank.id == tank_id).first()
    if not tank:
        raise HTTPException(status_code=404, detail="Tank not found")

    tank.name = tank_data.name
    tank.capacity = tank_data.capacity
    tank.is_active = tank_data.is_active

    db.commit()
    db.refresh(tank)

    return tank


@router.delete("/{tank_id}")
def delete_tank(tank_id: int, db: Session = Depends(get_db)):
    """절임조 삭제 (비활성화)"""
    tank = db.query(Tank).filter(Tank.id == tank_id).first()
    if not tank:
        raise HTTPException(status_code=404, detail="Tank not found")

    tank.is_active = False
    db.commit()

    return {"message": "Tank deactivated successfully"}
