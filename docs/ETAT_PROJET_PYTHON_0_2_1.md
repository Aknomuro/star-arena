# STAR ARENA Python 0.2.1 — Validation et Visual Fleet Update

> État initial du 4 novembre. Mise à jour du 5 novembre : les neuf PNG V9 sont
> désormais intégrés ; voir [le rapport d'intégration](ASSETS_PNG_INTEGRES.md).
> Les mentions d'assets manquants ci-dessous décrivent la livraison initiale.

Rapport du 4 novembre 2026. Mise à jour intégrée au même projet Python/Pygame CE.
Aucun lancement graphique, navigateur, Godot ou serveur MCP utilisé.

## Validation reçue et périmètre

L'utilisateur signale que les dix vérifications manuelles V0.2.0 ont réussi :
carte galactique, flottes, déplacements, batailles RTS, sélection multiple, tirs,
dégâts, destructions, conquêtes et sauvegardes. Cette validation utilisateur est
prise en compte ; elle n'a pas été répétée graphiquement par Codex.

La V0.2.1 conserve ce socle et le format JSON 2. Les caractéristiques d'armes,
coques, boucliers, vitesses, cadences, règles de capture et limites tactiques ne
sont pas rééquilibrées. Les changements de campagne corrigent les cas reproduits
ci-dessous ; les autres changements concernent la présentation et les contrôles.

## Tests complémentaires et corrections

Onze nouveaux tests de cas extrêmes ont été exécutés avant les corrections :
sept réussissaient, quatre échouaient. Les onze réussissent après correction.

| Cas | État final | Vérification |
|---|---|---|
| Une seule unité par flotte | OK logique | Duel naturel, résultat appliqué puis données rechargeables |
| Deux flottes entièrement détruites | OK logique | Résultat nul, aucun transfert de territoire, zéro survivant, sauvegarde et rechargement |
| Toutes les flottes vides | OK logique | Campagne rechargeable, ordres de mouvement refusés pour les flottes détruites |
| 200 participants | OK logique | 96 actifs au plus, réserves déployées par vagues, destruction des 200 unités sans résurrection |
| Arrivées alliées simultanées | CORRIGÉ | L'UID 25 d'une seconde flotte arrivant au même pas était exclu ; il participe maintenant au même engagement |
| Arrivées de deux factions sur un neutre | OK logique | Engagement à deux camps, identifiants uniques et état sauvegardable |
| Arrivées de trois factions | CORRIGÉ | Tous les trajets avancent du même pas ; le troisième camp garde son trajet terminé et intervient après le conflit courant |
| Conflits sur deux systèmes au même pas | CORRIGÉ | Le second trajet est avancé et conservé avant que le premier conflit ne suspende la campagne |
| Sauvegarde au milieu d'un voyage | OK logique | La reprise rejoint le même état que la simulation non interrompue |
| Identifiants et dégâts | OK logique | Trois cycles réels d'écriture/relecture conservent exactement les données du survivant endommagé |
| Défenseur gagnant dans un système resté neutre | CORRIGÉ | Le système restait sans propriétaire ; il appartient maintenant au vainqueur et l'état redevient sauvegardable |

### Traitement des arrivées

La campagne avance d'abord l'horloge de toutes les flottes en voyage, puis regroupe
les arrivées par destination. Tous les alliés arrivant pendant le même pas sont
présents avant la création de l'engagement. Les destinations sont traitées dans
un ordre stable ; les arrivées encore en attente gardent leur trajet et leurs UID.

Le combat reste à deux camps. Une troisième faction n'est ni supprimée ni ajoutée
artificiellement à un camp : son trajet reste terminé en attente, puis elle entre
dans le conflit suivant à la reprise de la campagne. La priorité d'occupation sans
défense reste déterministe par identifiant, comme dans la V0.2.

## Préparation graphique réalisée

- Catalogue de neuf emplacements : trois classes pour trois factions.
- Priorité au sprite de faction ; compatibilité avec l'ancien sprite générique ;
  recours au dessin vectoriel si aucun PNG utilisable n'est disponible.
- Secours vectoriel : coques blanc/bleu pour la République, gris foncé/rouge pour
  l'Empire, blanc cassé/orange pour l'Alliance, silhouettes angulaires par classe.
- Longueurs visuelles de référence distinctes : chasseur 42, corvette 72, croiseur
  112 unités, avec tailles minimales différentes au dézoom. Les hitboxes ne changent pas.
- Redimensionnement conservant le ratio, à l'arrondi au pixel près, au lieu de
  déformer toutes les images dans un rectangle de ratio imposé.
- Rotation via `rotozoom`, avec cache à pas d'un demi-degré au lieu des sauts de 15 degrés.
- Préservation de l'alpha par `convert_alpha`, sans détourage ni recoloration automatique.
- Original chargé une fois par chemin ; erreurs de décodage mémorisées pour éviter
  une nouvelle tentative chaque image. Un générique commun est partagé entre factions.
- Lecture préalable de 33 octets de l'en-tête PNG : signature, IHDR, CRC et dimensions.
- Limites avant décodage : 8 Mo, 4 096 pixels par dimension, quatre millions de pixels.
- Originaux réduits à 512 pixels au plus sur le grand côté en mémoire, sans modifier
  le fichier ; caches des tailles et des rotations limités en entrées et en pixels.
- Cache des tailles : 64 entrées / deux millions de pixels ; rotations : 256 entrées /
  quatre millions de pixels. Les unités hors champ évitent le travail de rendu.

Les fichiers PNG dédiés sont affichés avec leurs couleurs d'origine : ils devront
respecter les palettes attendues. Les palettes sont appliquées au secours vectoriel
et aux marqueurs de faction, pas utilisées pour repeindre automatiquement des images.

La représentation des flottes sur la carte reste symbolique ; les sprites unitaires
préparés ici concernent la scène RTS.

## Assets réellement intégrés et manquants

**PNG de vaisseaux réellement intégrés : aucun.**

L'inventaire de `assets/ships/` contient zéro PNG. Les PNG repérés dans l'ancienne
archive sont des captures de menus, cartes ou batailles, et ne sont pas utilisés
comme sprites transparents. Aucun PNG, image de substitution ou fichier PNG vide
n'a été généré, copié ou téléchargé.

| Faction | Chasseur | Corvette | Croiseur |
|---|---|---|---|
| République stellaire | `republic/fighter.png` — MANQUANT | `republic/corvette.png` — MANQUANT | `republic/cruiser.png` — MANQUANT |
| Empire galactique | `empire/fighter.png` — MANQUANT | `empire/corvette.png` — MANQUANT | `empire/cruiser.png` — MANQUANT |
| Alliance des mondes | `alliance/fighter.png` — MANQUANT | `alliance/corvette.png` — MANQUANT | `alliance/cruiser.png` — MANQUANT |

Chemins relatifs à `assets/ships/`. Les trois dossiers sont prêts. Les anciens
`assets/ships/fighter.png`, `corvette.png` et `cruiser.png` restent des emplacements
génériques compatibles, mais sont également absents.

**Le moteur est préparé ; les graphismes PNG ne sont pas terminés.**
Il reste à fournir de vrais sprites 2D vus de dessus, transparents, orientés à
droite, simples et nets, sans pixel art ni aspect cartoon mobile. Ajouter les
images avant le lancement ou redémarrer le jeu après leur ajout.

## Résultats vérifiés

| Contrôle | Résultat |
|---|---|
| Régressions V0.2 | 38 tests réussis |
| Cas extrêmes V0.2.1 | 11 tests réussis après correction |
| Catalogue, ratios, palettes et caches | 15 tests réussis |
| Total | **64 tests réussis, zéro échec, zéro erreur** |
| Temps de suite enregistré | Environ 0,22 s, un seul processus Python 3.12.14 |
| Import de Pygame pendant les tests | Aucun |
| Fichiers PNG créés par les tests | Aucun |
| Contrôle statique | **30 fichiers Python**, 63 imports locaux, 133 symboles importés, aucune erreur détectée |
| Inventaire graphique | Zéro PNG présent ; neuf emplacements de faction manquants |

Les tests du chargeur emploient un **backend factice sans surface graphique réelle**.
Ils vérifient les appels de cache, tailles, priorités de fichier et rotations, pas
le rendu Pygame. Les en-têtes synthétiques de test sont des octets en mémoire,
jamais des fichiers PNG sur disque. Le test de 200 participants vérifie les limites,
vagues et pertes, pas les FPS d'une longue bataille à 200 unités.

Preuves :

- `docs/LOGIC_TESTS_0_2_1.json`
- `docs/PYTHON_STATIC_CHECKS.json`
- `docs/SHIP_ASSETS_0_2_1.json`

Le rapport des tests V0.2, `LOGIC_TESTS_0_2.json`, est conservé. Le nouvel outil
de tests écrit désormais un rapport nommé d'après la version du paquet.

## Fichiers créés ou modifiés

Créés :

- `src/star_arena/presentation/fleet_assets.py`
- `src/star_arena/presentation/ship_sprites.py`
- `tests/test_extremes.py`, `tests/test_fleet_visuals.py`
- `tools/audit_ship_assets.py`
- Ce rapport et les preuves JSON V0.2.1 ; dossiers `republic`, `empire`, `alliance`

Modifiés :

- `systems/simulation.py` : arrivées groupées et temps de voyage cohérent
- `systems/combat.py` : propriété du système contesté après victoire
- `presentation/battle_renderer.py` : catalogue, caches et secours vectoriel par faction
- `src/star_arena/__init__.py`, `pyproject.toml` : version 0.2.1
- `tools/run_logic_tests.py` : rapport associé à la version
- `README.md`, `AGENTS.md`, `assets/ships/README.md` et lien dans le rapport historique V0.2

Les paramètres de `domain/ship_stats.py` et le format de sauvegarde 2 sont conservés.

## Vérification manuelle encore nécessaire

La validation utilisateur précédente concerne la V0.2.0. Le nouveau rendu vectoriel,
les futurs PNG, leur transparence, leur style, leur ratio et la rotation affichée
en V0.2.1 n'ont pas été contrôlés graphiquement par Codex. Aucun gain de fluidité ni
garantie de stabilité Windows n'est annoncé.

Lorsque l'utilisateur le décide :

```powershell
# Contrôles légers sans fenêtre
.\.venv\Scripts\python.exe -B tools\run_logic_tests.py --report
.\.venv\Scripts\python.exe -B tools\check_static.py --report
.\.venv\Scripts\python.exe -B tools\audit_ship_assets.py --report

# Lancement graphique exclusivement manuel
.\.venv\Scripts\python.exe main.py
```

En bataille, comparer les tailles des trois classes et les palettes des factions,
vérifier les silhouettes et les sélections, puis ajouter les vrais PNG et contrôler
leur rendu après redémarrage. Tant que ces images sont absentes, seul le secours
vectoriel est affiché.
