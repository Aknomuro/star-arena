from dataclasses import dataclass
from math import hypot

from star_arena.domain.models import Point


class GalaxyGeometry:
    """Une seule projection statique en cache, invalidée par caméra ou géométrie."""
    def __init__(self):
        self.key = None
        self.points = {}
        self.edges = ()

    def project(self, campaign, camera):
        key = (tuple((s.id, s.position) for s in campaign.systems.values()),
               frozenset(campaign.routes), camera.center, camera.scale, camera.viewport)
        if key != self.key:
            self.points = {i: camera.screen(s.position) for i, s in campaign.systems.items()}
            self.edges = tuple(sorted(campaign.routes))
            self.key = key
        return self.points


@dataclass
class Camera:
    center: Point = (0.0, 0.0)
    scale: float = 0.58
    viewport: tuple[int, int, int, int] = (20, 110, 876, 574)
    bounds: tuple[float, float, float, float] = (-1200.0, -1000.0, 1200.0, 1000.0)

    def screen(self, point: Point) -> tuple[int, int]:
        x, y, w, h = self.viewport
        return (round(x + w / 2 + (point[0] - self.center[0]) * self.scale),
                round(y + h / 2 + (point[1] - self.center[1]) * self.scale))

    def world(self, point: Point) -> Point:
        x, y, w, h = self.viewport
        return ((point[0] - x - w / 2) / self.scale + self.center[0],
                (point[1] - y - h / 2) / self.scale + self.center[1])

    def zoom(self, factor: float, anchor: Point) -> None:
        before = self.world(anchor)
        self.scale = min(1.4, max(0.12, self.scale * factor))
        after = self.world(anchor)
        self.center = self.center[0] + before[0] - after[0], self.center[1] + before[1] - after[1]
        self._constrain()

    def pan(self, dx: float, dy: float) -> None:
        self.center = self.center[0] - dx / self.scale, self.center[1] - dy / self.scale
        self._constrain()

    def follow_pointer(self, position: Point, dt: float) -> None:
        """Carré central immobile ; vitesse progressive vers les bords, en pixels/s."""
        x, y, w, h = self.viewport
        px, py = position
        if dt <= 0 or not (x <= px < x+w and y <= py < y+h):
            return
        half = min(w, h) * .25
        def axis(offset, extent):
            return max(-1., min(1., (abs(offset)-half)/(extent-half))) * (1 if offset > 0 else -1) if abs(offset) > half else 0.
        vx = axis(px-(x+w/2), w/2)
        vy = axis(py-(y+h/2), h/2)
        length = max(1., hypot(vx, vy))
        self.pan(-vx/length * 520 * dt, -vy/length * 520 * dt)

    def _constrain(self) -> None:
        left, top, right, bottom = self.bounds
        self.center = max(left, min(right, self.center[0])), max(top, min(bottom, self.center[1]))
