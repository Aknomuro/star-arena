"""Recherche locale de voisins, indépendante de Pygame."""
from collections import defaultdict
from math import floor


class SpatialGrid:
    def __init__(self, cell_size: float = 240.0) -> None:
        self.cell_size = cell_size
        self.cells: dict[tuple[int, int], list] = {}

    def rebuild(self, units) -> None:
        cells = defaultdict(list)
        for unit in units:
            if unit.ship.alive:
                cells[(floor(unit.x / self.cell_size), floor(unit.y / self.cell_size))].append(unit)
        self.cells = dict(cells)

    def near(self, x: float, y: float, radius: float):
        r2 = radius * radius
        for cx in range(floor((x - radius) / self.cell_size), floor((x + radius) / self.cell_size) + 1):
            for cy in range(floor((y - radius) / self.cell_size), floor((y + radius) / self.cell_size) + 1):
                for unit in self.cells.get((cx, cy), ()):
                    if unit.ship.alive and (unit.x - x)**2 + (unit.y - y)**2 <= r2:
                        yield unit
