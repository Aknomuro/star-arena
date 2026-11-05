"""Données d'équilibrage planétaire, indépendantes du rendu et de la simulation."""
PLANET_TYPES = {
    'rocky': ('Rocheuse', 3), 'desert': ('Désertique', 2), 'ice': ('Glacée', 2),
    'ocean': ('Océanique', 1), 'gas': ('Gazeuse', 4), 'industrial': ('Industrielle', 3),
}
# crédits, minerais, secondes (multipliés par le niveau acheté)
GROUND = {
    'mine': ('Mine', 120, 65, 15), 'power': ('Centrale', 100, 45, 12),
    'trade': ('Centre commercial', 140, 50, 18), 'industry': ('Industrie', 200, 100, 24),
    'recruit': ('Centre de recrutement', 110, 40, 15), 'barracks': ('Caserne', 160, 70, 20),
    'garrison': ('Garnison planétaire', 220, 100, 25),
}
# nom, coque, bouclier, tourelles, capacité chasseurs, capacité corvettes, réparation/s, entretien/s
STATIONS = {
    1: ('Avant-poste orbital', 1400., 600., 2, 2, 0, 1., 1),
    2: ('Station militaire', 2600., 1200., 4, 4, 0, 2., 2),
    3: ('Forteresse orbitale', 4300., 2200., 6, 6, 1, 4., 3),
    4: ('Citadelle stellaire', 6500., 3600., 8, 10, 2, 6., 4),
}
STATION_COSTS = {1:(300,150,30), 2:(500,260,45), 3:(800,430,65), 4:(1200,650,90)}
# nom, crédits, minerais, temps, coque, bouclier, dégâts, portée
DEFENSES = {
    'laser': ('Plateforme anti-chasseur', 160,80,20,600.,220.,10.,520.),
    'missile': ('Batterie anti-croiseur', 240,120,28,800.,180.,35.,700.),
    'heavy': ('Tourelle lourde', 280,150,30,1100.,350.,24.,600.),
    'shield': ('Générateur de boucliers', 230,130,26,700.,650.,2.,430.),
    'repair': ('Station de réparation', 210,100,24,750.,250.,2.,430.),
    'radar': ('Relais radar', 150,70,18,500.,150.,2.,900.),
}
ORBITAL_TYPES = {f'station{n}': (v[0], v[1], v[2]) for n,v in STATIONS.items()}
ORBITAL_TYPES.update({k:(v[0],v[4],v[5]) for k,v in DEFENSES.items()})
