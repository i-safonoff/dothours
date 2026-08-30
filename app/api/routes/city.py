from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.building_families import BUILDING_FAMILIES
from app.models.city import CityBuilding
from app.models.enums import OwnerType
from app.models.user import User
from app.schemas.city import BuildingFamilyOut, CityBuildingOut, CityDistrictOut, CityOut
from app.services.city_layout import place_missing, sync_districts

router = APIRouter(tags=["city"])


@router.get("/building-families", response_model=list[BuildingFamilyOut])
def list_building_families() -> list[BuildingFamilyOut]:
    return [BuildingFamilyOut.model_validate(family.model_dump()) for family in BUILDING_FAMILIES.values()]


@router.get("/city/districts", response_model=list[CityDistrictOut])
def list_districts(db: Session = Depends(get_db)) -> list[CityDistrictOut]:
    """Static catalog, synced from code on first read."""
    districts = sync_districts(db)
    db.commit()
    return [CityDistrictOut.model_validate(d) for d in districts]


@router.get("/city/me", response_model=CityOut)
def get_my_city(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CityOut:
    buildings = list(
        db.scalars(
            select(CityBuilding).where(
                CityBuilding.owner_type == OwnerType.user, CityBuilding.owner_id == current_user.id
            )
        ).all()
    )
    place_missing(db, buildings)
    return CityOut(buildings=[CityBuildingOut.model_validate(b) for b in buildings])
