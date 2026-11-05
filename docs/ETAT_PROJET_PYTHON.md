# STAR ARENA: GALACTIC CONQUEST — état du projet Python

> Rapport historique de la V0.1.0. État actuel : [V0.2.1](ETAT_PROJET_PYTHON_0_2_1.md).

Rapport du 4 novembre 2026, fondé sur la lecture des fichiers actuels. Version
déclarée : **Python 0.1.0**. Ce rapport concerne uniquement la reconstruction Python.

**Présent** signifie implémenté dans les sources ; cela ne signifie pas validé
par un lancement interactif. Aucun jeu, test graphique ou navigateur lancé pour
ce rapport.

## Fonctionnalités présentes

| Domaine | Contenu implémenté | Source principale |
|---|---|---|
| Menu | Nouvelle campagne, choix de faction, reprise, chargement, quitter | `src/star_arena/app.py`, `presentation/renderer.py` |
| Factions | République stellaire, Empire galactique, Alliance des mondes ; couleurs et descriptions | `domain/models.py` |
| Carte | 15 systèmes nommés, 26 routes directes, trois capitales et 12 systèmes neutres au départ | `domain/galaxy.py` |
| Génération | Positions reproductibles par graine, graine 42 utilisée au lancement | `domain/galaxy.py`, `config.py` |
| Flottes | Trois flottes initiales, une par faction ; huit vaisseaux par flotte, 24 au total | `domain/galaxy.py` |
| Vaisseaux | Chasseurs, corvettes et croiseurs ; identifiant individuel, modèle, coque et bouclier | `domain/models.py` |
| Sélection | Systèmes et flottes par clic, sélection des flottes par Tab, panneau de composition | `app.py`, `presentation/renderer.py` |
| Déplacements | Ordres sur routes voisines, mouvement interpolé, progression et temps restant ; refus d'un second trajet pendant le transit | `systems/simulation.py` |
| Territoires | Occupation des systèmes neutres à l'arrivée d'une flotte | `systems/simulation.py` |
| IA | Les deux factions non jouées explorent les voisins neutres, puis circulent en territoire allié ; décisions toutes les six secondes simulées | `systems/simulation.py` |
| Conflits provisoires | Attaque d'un système hostile refusée ; repli si un système devient hostile pendant l'approche | `systems/simulation.py`, `systems/combat.py` |
| Temps | Pause, vitesses ×1/×2/×4, simulation par pas de 0,1 seconde | `app.py`, `systems/simulation.py` |
| Caméra | Zoom à la souris, déplacement au bouton du milieu, recentrage sur le système sélectionné | `presentation/camera.py`, `app.py` |
| Journal | Douze derniers événements conservés ; trois visibles dans le panneau | `domain/models.py`, `presentation/renderer.py` |
| Sauvegardes | Sauvegarde et chargement manuels JSON, état des systèmes, flottes, vaisseaux, trajets, horloge et fraction de pas | `persistence.py` |
| Validation des fichiers | Identifiants uniques, routes, capitales, nombres, états et tailles contrôlés ; données incompatibles protégées | `persistence.py` |
| Écriture des sauvegardes | Temporaire unique, synchronisation et remplacement atomique dans le dossier cible | `persistence.py` |

### Composition de départ de chaque flotte

| Modèle | Quantité | Coque par vaisseau | Bouclier par vaisseau |
|---|---:|---:|---:|
| Croiseur | 1 | 1 500 | 800 |
| Corvette | 2 | 480 | 220 |
| Chasseur | 5 | 100 | 60 |

Les coques et boucliers sont actuellement des données conservées ; il n'y a pas
encore de tirs ni de dégâts en jeu. Les factions partagent les mêmes modèles et
statistiques : aucun bonus de faction n'est implémenté. La vitesse de déplacement
galactique est commune aux flottes, indépendamment de leur composition.

### Règles de territoire actuelles

Un système neutre est occupé à l'arrivée d'une flotte. Un système allié peut être
rejoint sans changer de propriétaire. Un ordre vers un système hostile est refusé.
Si deux factions convoitent le même système neutre, la seconde flotte qui trouve
une présence hostile repart vers son origine. Aucune victoire militaire n'est
calculée par ce mécanisme.

## Architecture préparée pour la suite

| Élément | État réel |
|---|---|
| Simulation indépendante de Pygame | Présente : modèles et systèmes séparés du rendu |
| Contrat de rencontre `Encounter` / `CombatResolver` | Présent, mais le résolveur actuel refuse l'occupation hostile |
| Contrat `EconomySystem` | Présent, mais l'implémentation active `NoEconomy` ne produit et ne dépense rien |
| Identifiants individuels des vaisseaux | Présents pour préparer les pertes et survivants futurs |
| Format de sauvegarde | Format Python 1 ; fraction de pas optionnelle pour les fichiers antérieurs |
| VS Code | Interpréteur `.venv`, chemins d'analyse et lancement F5 manuel configurés |

Un fichier de combat ou d'économie ne constitue donc pas encore une fonctionnalité
de combat ou d'économie jouable.

## Fonctionnalités absentes

- Batailles RTS, armes, projectiles, dégâts, destruction et calcul des survivants.
- Conquête de systèmes ennemis et résolution militaire automatique.
- Ressources économiques, revenus, dépenses, entretien, pénuries et commerce.
- Bâtiments, mines, centrales, chantiers navals et production de nouveaux vaisseaux.
- Colonisation avec vaisseau spécialisé, coût ou délai : seule l'occupation neutre existe.
- Création, division et fusion de flottes depuis l'interface.
- Amiraux, expérience, doctrines, formations de combat, sièges et renforts tactiques.
- Ordres multi-sauts, files d'ordres, diplomatie et conditions de victoire ou défaite.
- Audio, multijoueur, import des sauvegardes Godot et export Web validé.

## Réglages et optimisations présents

- Fenêtre fixe 1280 × 800, cible limitée à 30 images par seconde.
- Surfaces SDL classiques ; aucune demande OpenGL, audio ou plein écran.
- Simulation et rendu suspendus en arrière-plan ; boucle d'événements limitée à 10 Hz.
- Nombre de pas de rattrapage limité à cinq par image.
- Fond étoilé construit une fois ; cache LRU de texte limité à 256 entrées et
  deux millions de pixels.
- Coordonnées des systèmes réutilisées dans chaque image ; éléments éloignés de
  la zone visible omis du dessin.
- Analyse VS Code limitée aux fichiers ouverts et indexation Pylance désactivée.

Ces réglages existent dans le code. Aucun gain mesuré de FPS, consommation mémoire
ou résultat de stabilité Windows n'est annoncé.

## Environnement observé sur disque

- Dossier `.venv` présent et fichier `.venv/Scripts/python.exe` présent.
- `.venv/pyvenv.cfg` déclare **Python 3.15.0**.
- Les métadonnées locales déclarent **pygame-ce 2.5.8** et le paquet `pygame` est présent.
- Le projet demande Python 3.11+ et déclare `pygame-ce>=2.5,<3`.

Ces informations proviennent des fichiers de configuration et des métadonnées,
sans exécuter l'interpréteur du jeu ni importer Pygame. Elles ne prouvent pas
que l'affichage ou les extensions natives fonctionnent sur la machine.

## Vérifications disponibles

Le dernier rapport statique enregistré, `PYTHON_STATIC_CHECKS.json`, indique :

- **17 fichiers Python** analysés ;
- **23 imports locaux** et **51 symboles importés** contrôlés ;
- **aucune erreur détectée** dans ce périmètre ;
- analyse de syntaxe Python 3.11, dépendances, versions, séparation simulation/rendu
  et configurations VS Code.

Le rendu, les clics, les déplacements, les sauvegardes en conditions réelles,
les performances et la stabilité du jeu restent **NON TESTÉS par Codex** pour
cette version Python. Le contrôle statique n'est pas un certificat de stabilité.

## Points d'entrée et documentation

- Lancement manuel : `main.py`.
- Dépendances : `requirements.txt` et `pyproject.toml`.
- Guide d'installation et commandes : `README.md`.
- Outil de contrôle statique : `tools/check_static.py`.
- Corrections et optimisations de la dernière révision : `docs/REVISION_PYTHON.md`.

Pour lancer depuis l'environnement du projet, lorsque l'utilisateur le décide :

```powershell
.\.venv\Scripts\python.exe main.py
```
