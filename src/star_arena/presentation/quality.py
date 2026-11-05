"""Profils de présentation uniquement : aucune modification des règles militaires."""
from dataclasses import dataclass

@dataclass(frozen=True)
class QualityProfile:
    name: str
    angle_step: float
    size_step: int
    max_effects: int
    debris: int

DESKTOP=QualityProfile('Desktop',.5,1,100,3)
REDUCED=QualityProfile('Web / réduit',2.,4,32,0)

def profile(reduced: bool):
    return REDUCED if reduced else DESKTOP
