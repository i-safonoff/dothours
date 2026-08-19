"""Static catalog of building families and their level thresholds.

Not a database table on purpose — this is product config, not user data.
See docs/API_SPEC.md, Приложение А.
"""

from pydantic import BaseModel


class BuildingLevel(BaseModel):
    level: int
    title: str
    hours_threshold: int


class BuildingFamily(BaseModel):
    key: str
    title: str
    levels: list[BuildingLevel]


BUILDING_FAMILIES: dict[str, BuildingFamily] = {
    "sport": BuildingFamily(
        key="sport",
        title="Спорт",
        levels=[
            BuildingLevel(level=1, title="Спортплощадка", hours_threshold=0),
            BuildingLevel(level=2, title="Тренажёрный зал", hours_threshold=10),
            BuildingLevel(level=3, title="Спортшкола", hours_threshold=30),
            BuildingLevel(level=4, title="Стадион", hours_threshold=80),
            BuildingLevel(level=5, title="Олимпийский комплекс", hours_threshold=150),
        ],
    ),
    "study": BuildingFamily(
        key="study",
        title="Учёба",
        levels=[
            BuildingLevel(level=1, title="Класс", hours_threshold=0),
            BuildingLevel(level=2, title="Школа", hours_threshold=10),
            BuildingLevel(level=3, title="Библиотека", hours_threshold=30),
            BuildingLevel(level=4, title="Университет", hours_threshold=80),
            BuildingLevel(level=5, title="Институт", hours_threshold=150),
        ],
    ),
    "work": BuildingFamily(
        key="work",
        title="Работа",
        levels=[
            BuildingLevel(level=1, title="Гараж-стартап", hours_threshold=0),
            BuildingLevel(level=2, title="Офис", hours_threshold=10),
            BuildingLevel(level=3, title="Бизнес-центр", hours_threshold=30),
            BuildingLevel(level=4, title="Технопарк", hours_threshold=80),
            BuildingLevel(level=5, title="Штаб-квартира", hours_threshold=150),
        ],
    ),
    "creativity": BuildingFamily(
        key="creativity",
        title="Творчество",
        levels=[
            BuildingLevel(level=1, title="Мастерская", hours_threshold=0),
            BuildingLevel(level=2, title="Студия", hours_threshold=10),
            BuildingLevel(level=3, title="Галерея", hours_threshold=30),
            BuildingLevel(level=4, title="Театр", hours_threshold=80),
            BuildingLevel(level=5, title="Культурный квартал", hours_threshold=150),
        ],
    ),
    "meditation": BuildingFamily(
        key="meditation",
        title="Осознанность",
        levels=[
            BuildingLevel(level=1, title="Уголок тишины", hours_threshold=0),
            BuildingLevel(level=2, title="Сад", hours_threshold=10),
            BuildingLevel(level=3, title="Храм", hours_threshold=30),
            BuildingLevel(level=4, title="Ретрит-центр", hours_threshold=80),
            BuildingLevel(level=5, title="Гора просветления", hours_threshold=150),
        ],
    ),
    "reading": BuildingFamily(
        key="reading",
        title="Чтение",
        levels=[
            BuildingLevel(level=1, title="Книжная полка", hours_threshold=0),
            BuildingLevel(level=2, title="Читальня", hours_threshold=10),
            BuildingLevel(level=3, title="Библиотека", hours_threshold=30),
            BuildingLevel(level=4, title="Книжный квартал", hours_threshold=80),
            BuildingLevel(level=5, title="Нац. библиотека", hours_threshold=150),
        ],
    ),
    "custom": BuildingFamily(
        key="custom",
        title="Своё дело",
        levels=[
            BuildingLevel(level=1, title="Фундамент", hours_threshold=0),
            BuildingLevel(level=2, title="Постройка", hours_threshold=10),
            BuildingLevel(level=3, title="Здание", hours_threshold=30),
            BuildingLevel(level=4, title="Комплекс", hours_threshold=80),
            BuildingLevel(level=5, title="Достопримечательность", hours_threshold=150),
        ],
    ),
}


def level_for_hours(family_key: str, total_hours: float) -> int:
    family = BUILDING_FAMILIES[family_key]
    level = 1
    for building_level in family.levels:
        if total_hours >= building_level.hours_threshold:
            level = building_level.level
    return level
