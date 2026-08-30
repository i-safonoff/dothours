"""Placing buildings on the isometric grid (Этап 7).

Placement is deterministic from the building's id: the same city renders the
same way on every client and after every restart, without storing a layout
algorithm's state. A building's district follows from its family; the exact
tile inside the district is what makes two cities with the same buildings look
different from each other.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.city_districts import CITY_DISTRICTS, DISTRICTS_BY_FAMILY, VARIANTS_PER_FAMILY
from app.models.city import CityBuilding, CityDistrict

ROTATIONS = (0, 90, 180, 270)


def sync_districts(db: Session) -> list[CityDistrict]:
    """Upsert the code catalog into the table. Idempotent, cheap, safe to call on read."""
    existing = {district.key: district for district in db.scalars(select(CityDistrict)).all()}

    for spec in CITY_DISTRICTS:
        district = existing.get(spec.key)
        if district is None:
            district = CityDistrict(key=spec.key)
            db.add(district)
            existing[spec.key] = district
        district.building_family = spec.building_family
        district.title = spec.title
        district.grid_x = spec.grid_x
        district.grid_y = spec.grid_y
        district.grid_w = spec.grid_w
        district.grid_h = spec.grid_h

    db.flush()
    return [existing[spec.key] for spec in CITY_DISTRICTS]


def _seed(building_id: uuid.UUID, salt: int) -> int:
    return (building_id.int >> salt) & 0xFFFF


def assign_placement(db: Session, building: CityBuilding) -> CityBuilding:
    """Give a building its district, tile, rotation and visual variant.

    Idempotent: a building that already has a district keeps its spot, so a
    city never shuffles itself between requests.
    """
    if building.district_id is not None:
        return building

    # Freshly constructed rows still hold a plain string; loaded ones hold the enum.
    family = getattr(building.building_family, "value", building.building_family)
    spec = DISTRICTS_BY_FAMILY.get(family)
    if spec is None:
        return building

    district = db.scalar(select(CityDistrict).where(CityDistrict.key == spec.key))
    if district is None:
        sync_districts(db)
        district = db.scalar(select(CityDistrict).where(CityDistrict.key == spec.key))
        if district is None:
            return building

    building.district_id = district.id
    building.position_x = district.grid_x + _seed(building.id, 0) % district.grid_w
    building.position_y = district.grid_y + _seed(building.id, 16) % district.grid_h
    building.rotation = ROTATIONS[_seed(building.id, 32) % len(ROTATIONS)]
    building.variant = 1 + _seed(building.id, 48) % VARIANTS_PER_FAMILY
    db.flush()
    return building


def place_missing(db: Session, buildings: list[CityBuilding]) -> list[CityBuilding]:
    """Backfill for buildings created before this stage existed."""
    unplaced = [b for b in buildings if b.district_id is None]
    if not unplaced:
        return buildings

    sync_districts(db)
    for building in unplaced:
        assign_placement(db, building)
    db.commit()
    return buildings
