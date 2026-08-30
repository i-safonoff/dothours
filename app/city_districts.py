"""Static catalog of city districts (Этап 7).

Like `building_families`, this is product config rather than user data — it
lives in code and is synced into the `city_districts` table, which exists only
so a building can point at a district by foreign key.

The grid is in abstract tiles; the frontend decides how big a tile is on
screen. Districts do not overlap, and the centre square at (0,0) is deliberately
left as a shared plaza with no family attached.
"""

from pydantic import BaseModel


class CityDistrictSpec(BaseModel):
    key: str
    building_family: str | None
    title: str
    grid_x: int
    grid_y: int
    grid_w: int
    grid_h: int


CITY_DISTRICTS: list[CityDistrictSpec] = [
    CityDistrictSpec(key="plaza", building_family=None, title="Площадь", grid_x=0, grid_y=0, grid_w=4, grid_h=4),
    CityDistrictSpec(
        key="sport", building_family="sport", title="Спортивный квартал", grid_x=-6, grid_y=0, grid_w=5, grid_h=5
    ),
    CityDistrictSpec(
        key="study", building_family="study", title="Студенческий городок", grid_x=6, grid_y=0, grid_w=5, grid_h=5
    ),
    CityDistrictSpec(key="work", building_family="work", title="Деловой центр", grid_x=0, grid_y=6, grid_w=5, grid_h=5),
    CityDistrictSpec(
        key="creativity",
        building_family="creativity",
        title="Творческий квартал",
        grid_x=0,
        grid_y=-6,
        grid_w=5,
        grid_h=5,
    ),
    CityDistrictSpec(
        key="meditation", building_family="meditation", title="Тихий сад", grid_x=-6, grid_y=-6, grid_w=5, grid_h=5
    ),
    CityDistrictSpec(
        key="reading", building_family="reading", title="Библиотечный квартал", grid_x=6, grid_y=-6, grid_w=5, grid_h=5
    ),
    CityDistrictSpec(key="custom", building_family="custom", title="Окраина", grid_x=6, grid_y=6, grid_w=5, grid_h=5),
]

DISTRICTS_BY_FAMILY: dict[str, CityDistrictSpec] = {
    district.building_family: district for district in CITY_DISTRICTS if district.building_family is not None
}

VARIANTS_PER_FAMILY = 3
