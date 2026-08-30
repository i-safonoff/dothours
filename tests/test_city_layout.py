from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.city_districts import CITY_DISTRICTS, DISTRICTS_BY_FAMILY
from app.models.city import CityBuilding, CityDistrict
from app.services.city_layout import assign_placement, sync_districts
from tests.conftest import auth_headers, register_and_login
from tests.test_categories import create_category
from tests.test_companies import create_company, invite_and_join, log_minutes


def test_districts_catalog_is_served_and_synced_once(client: TestClient, db_session: Session) -> None:
    response = client.get("/api/v1/city/districts")
    assert response.status_code == 200

    districts = response.json()
    assert {d["key"] for d in districts} == {spec.key for spec in CITY_DISTRICTS}
    assert [d["key"] for d in districts] == [spec.key for spec in CITY_DISTRICTS]

    plaza = next(d for d in districts if d["key"] == "plaza")
    assert plaza["building_family"] is None

    client.get("/api/v1/city/districts")
    assert db_session.query(CityDistrict).count() == len(CITY_DISTRICTS)


def test_districts_do_not_overlap() -> None:
    tiles: set[tuple[int, int]] = set()
    for spec in CITY_DISTRICTS:
        for x in range(spec.grid_x, spec.grid_x + spec.grid_w):
            for y in range(spec.grid_y, spec.grid_y + spec.grid_h):
                assert (x, y) not in tiles, f"район {spec.key} налезает на соседа в ({x}, {y})"
                tiles.add((x, y))


def test_new_building_is_placed_in_its_family_district(client: TestClient, db_session: Session) -> None:
    session = register_and_login(client)
    category = create_category(client, session["token"], building_family="sport")
    log_minutes(client, session["token"], category["id"], 90)

    city = client.get("/api/v1/city/me", headers=auth_headers(session["token"])).json()
    building = city["buildings"][0]

    district = db_session.query(CityDistrict).filter(CityDistrict.key == "sport").one()
    spec = DISTRICTS_BY_FAMILY["sport"]

    assert building["district_id"] == str(district.id)
    assert spec.grid_x <= building["position_x"] < spec.grid_x + spec.grid_w
    assert spec.grid_y <= building["position_y"] < spec.grid_y + spec.grid_h
    assert building["rotation"] in (0, 90, 180, 270)
    assert 1 <= building["variant"] <= 3


def test_placement_is_stable_across_reads_and_level_ups(client: TestClient) -> None:
    session = register_and_login(client)
    category = create_category(client, session["token"], building_family="study", shape="square")
    log_minutes(client, session["token"], category["id"], 90)

    first = client.get("/api/v1/city/me", headers=auth_headers(session["token"])).json()["buildings"][0]
    log_minutes(client, session["token"], category["id"], 60 * 20)  # уровень вырос
    second = client.get("/api/v1/city/me", headers=auth_headers(session["token"])).json()["buildings"][0]

    assert second["level"] > first["level"]
    assert (second["position_x"], second["position_y"]) == (first["position_x"], first["position_y"])
    assert second["variant"] == first["variant"]
    assert second["rotation"] == first["rotation"]


def test_buildings_of_different_families_land_in_different_districts(client: TestClient) -> None:
    session = register_and_login(client)
    sport = create_category(client, session["token"], building_family="sport")
    reading = create_category(client, session["token"], building_family="reading", title="Чтение", shape="hex")
    log_minutes(client, session["token"], sport["id"], 60)
    log_minutes(client, session["token"], reading["id"], 60)

    buildings = client.get("/api/v1/city/me", headers=auth_headers(session["token"])).json()["buildings"]
    assert len({b["district_id"] for b in buildings}) == 2


def test_legacy_building_without_a_district_is_backfilled(client: TestClient, db_session: Session) -> None:
    session = register_and_login(client)
    category = create_category(client, session["token"], building_family="work", shape="triangle")
    log_minutes(client, session["token"], category["id"], 60)

    building = db_session.query(CityBuilding).one()
    building.district_id = None  # как будто строка создана до Этапа 7
    building.position_x = building.position_y = 0
    db_session.commit()

    city = client.get("/api/v1/city/me", headers=auth_headers(session["token"])).json()
    assert city["buildings"][0]["district_id"] is not None


def test_company_city_is_laid_out_too(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    company = create_company(client, ann["token"])
    invite_and_join(client, ann["token"], company["id"], bob["token"])

    category = create_category(client, bob["token"], building_family="creativity", shape="blob")
    log_minutes(client, bob["token"], category["id"], 120)

    city = client.get(f"/api/v1/companies/{company['id']}/city", headers=auth_headers(ann["token"])).json()
    assert city["buildings"][0]["district_id"] is not None


def test_placement_is_idempotent(client: TestClient, db_session: Session) -> None:
    session = register_and_login(client)
    category = create_category(client, session["token"], building_family="meditation", shape="diamond")
    log_minutes(client, session["token"], category["id"], 60)

    sync_districts(db_session)
    building = db_session.query(CityBuilding).one()
    before = (building.district_id, building.position_x, building.position_y, building.rotation, building.variant)

    assign_placement(db_session, building)
    after = (building.district_id, building.position_x, building.position_y, building.rotation, building.variant)
    assert after == before
