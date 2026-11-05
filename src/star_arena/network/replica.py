"""Vue cliente sans horloge de simulation ni méthode de mutation autorisée."""
from star_arena.systems.simulation import Simulation
from star_arena.systems.navigation import RoutePlanner


class CampaignReplica:
    def __init__(self,campaign):
        self.campaign=campaign
        self.planner=RoutePlanner(campaign)

    # La validation d'interface est pure ; les dépenses et déplacements restent sur l'hôte.
    movement_error=Simulation.movement_error

    def advance(self,dt):
        raise RuntimeError('Une copie cliente ne peut pas simuler la campagne.')

    def order_move(self,*args,**kwargs):
        raise RuntimeError('Envoyer une commande à l’hôte au lieu de modifier la copie.')
