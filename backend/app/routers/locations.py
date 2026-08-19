"""常用位置路由。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import UserLocationCreate, UserLocationOut
from ..services import restaurant_service

router = APIRouter(prefix="/api/locations", tags=["locations"])


@router.get("", response_model=list[UserLocationOut])
def list_locations(db: Session = Depends(get_db)):
    return restaurant_service.list_locations(db)


@router.post("", response_model=UserLocationOut, status_code=201)
def create_location(payload: UserLocationCreate, db: Session = Depends(get_db)):
    return restaurant_service.create_location(db, payload)


@router.delete("/{location_id}", status_code=204)
def delete_location(location_id: int, db: Session = Depends(get_db)):
    if not restaurant_service.delete_location(db, location_id):
        raise HTTPException(404, "位置不存在")
