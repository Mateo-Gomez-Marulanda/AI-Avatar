from alive.domain.config import Zone
from alive.domain.geometry import Rect, nearest_zone, zone_rect

MON = Rect(0, 0, 1920, 1080)
SZ = (200, 300)

def test_top_zone_sits_below_panel_without_covering_it():
    r = zone_rect(MON, Zone("top", margin=32), SZ)
    assert (r.x, r.y, r.width, r.height) == (860, 32, 200, 300)

def test_side_zones_and_floating():
    assert zone_rect(MON, Zone("left", margin=10), SZ).x == 10
    assert zone_rect(MON, Zone("right", margin=10), SZ).x == 1710
    assert zone_rect(MON, Zone("floating", x=100, y=200), SZ).y == 200

def test_nearest_zone_picks_closest_edge():
    zones = {"barra": Zone("top", 32), "izq": Zone("left", 10), "der": Zone("right", 10)}
    assert nearest_zone(MON, (5, 500), zones, SZ) == "izq"
    assert nearest_zone(MON, (1910, 500), zones, SZ) == "der"
