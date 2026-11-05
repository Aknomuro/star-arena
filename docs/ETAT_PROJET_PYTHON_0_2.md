# STAR ARENA Python 0.2.0 — Space Warfare

> Rapport historique V0.2.0. L'utilisateur signale dix tests manuels réussis.
> État actuel : [V0.2.1](ETAT_PROJET_PYTHON_0_2_1.md).

Livraison du 4 novembre 2026. Mise à jour intégrée au projet Python existant,
sans Godot, serveur MCP ni lancement graphique. L'économie n'a pas été développée.

## Audit du socle et préservation

Lecture préalable de `ETAT_PROJET_PYTHON.md` et des sources actives. La carte à
15 systèmes et 26 routes, les trois factions et leurs trois flottes de huit
vaisseaux sont conservées. Les identifiants, modèles, coques et boucliers existants
restent la référence du combat. Les commandes de campagne, les routes, les vitesses
temporelles, la caméra et les sauvegardes ont été conservées.

Le résolveur qui refusait les attaques ennemies a été remplacé par le traitement
des engagements. Le moteur de campagne a été étendu aux arrivées militaires ;
la simulation tactique est un module séparé et indépendant de Pygame.

## Fonctionnalités terminées dans le code

| Fonction | Implémentation et limites de validation |
|---|---|
| Attaque d'un système ennemi | Ordre accepté sur une route directe ; occupation immédiate si aucune flotte adverse n'est présente |
| Engagement | Arrivée de forces opposées, participants réels, notification et suspension de la campagne |
| Entrée dans le RTS | Bouton « Commander la bataille RTS » ; scène rendue dans la fenêtre existante |
| Champ de bataille | 3 200 × 2 000 unités, fond spatial, quatorze astéroïdes non superposés à la génération |
| Vaisseaux réels | Objets `Ship` existants utilisés directement ; même identifiant, coque et bouclier |
| Commandes | Clic, rectangle, Maj, déplacement, attaque ciblée, attaque-déplacement, arrêt, tenir et groupes 1–9 |
| Formations | Ligne, coin et compacte, boutons RTS et espacement des destinations |
| Mouvement | Vitesses et rotations par classe, séparation locale, contournement simple et exclusion des astéroïdes |
| Armes | Lasers, portée, cadence, projectiles avec collision segment/cercle ; quatre tourelles autonomes sur le croiseur |
| Dégâts | Bouclier absorbant avant la coque ; destruction à zéro, aucune réapparition d'un UID détruit |
| Effets | Impacts de bouclier, explosions et débris simples, sous budget limité |
| IA tactique | Décisions périodiques, priorités de cible, distance d'engagement, protection des croiseurs et nouvelle cible après destruction |
| IA galactique | Expansion conservée ; attaques des voisins ennemis vulnérables, combats IA/IA résolus abstraitement |
| Résolution automatique | Dégâts, cadence, tourelles, bonus de cible, coque et bouclier réels ; générateur aléatoire local reproductible |
| Retour campagne | Pertes retirées, dégâts conservés, flottes vides mémorisées, repli ou capture des perdants |
| Conquête | Transfert du système après victoire de l'attaquant ; sans défense, occupation directe |
| Rapport | Vainqueur, système, engagés, détruits, survivants, capturés, croiseurs et résultat territorial ; pagination des croiseurs |
| Sauvegardes | Format 2, migration en mémoire du format 1, dégâts, pertes, conquêtes, engagements en attente et rapports |

**Le moteur de logique est testé. Le rendu et les interactions Pygame ne sont
pas testés graphiquement.** Les fonctions de présentation du tableau sont implémentées,
mais leur validation visuelle est laissée à l'utilisateur.

### Caractéristiques tactiques

| Classe | Coque | Bouclier | Vitesse | Rotation rad/s | Portée | Dégâts / tir | Recharge s | Tourelles | Vitesse projectile |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Chasseur | 100 | 60 | 145 | 4,5 | 260 | 5 | 0,24 | 1 | 800 |
| Corvette | 480 | 220 | 90 | 2,5 | 390 | 13 | 0,60 | 2 | 720 |
| Croiseur | 1 500 | 800 | 48 | 1 | 560 | 30 | 1,25 | 4 | 650 |

Multiplicateurs : chasseur contre chasseur ×1,25 ; corvette contre chasseur ×1,55 ;
croiseur contre corvette ou croiseur ×1,30. Ces paramètres sont centralisés dans
`domain/ship_stats.py`. Les valeurs de coque/bouclier historiques ne changent pas.

### Règles de résultat et de repli

- Le camp sans vaisseau vivant perd ; si les deux camps sont éliminés, le résultat est nul.
- L'attaquant survivant qui gagne prend le système. Un résultat nul conserve le territoire.
- Le bouton de repli concède la bataille. Les survivants gardent leurs dégâts.
- Les perdants rejoignent un système allié directement voisin, de préférence
  l'origine de l'attaque, par un trajet réel. Sans refuge voisin, ils sont capturés.
- Les capturés sont distincts des détruits dans le rapport et ne restent pas dans les flottes.
- Les flottes annihilées ou capturées restent enregistrées avec une liste de vaisseaux vide.
- L'application du résultat est idempotente : un second retour ne recrée ni flotte ni vaisseau.
- La résolution IA abstraite dure au plus 180 salves. Si les deux camps survivent,
  leur puissance restante décide du vainqueur ; le perdant se replie ou est capturé.
- Une occupation sans défense est signalée au journal, sans bataille fictive.

### Sauvegardes

Le fichier local reste `saves/campaign.json`. Le format 1 de la V0.1 est accepté
et migré en mémoire sans ajout de vaisseaux, dégâts réparés ou récompense. L'original
n'est pas réécrit au chargement ; une sauvegarde manuelle ultérieure écrit le format 2.
Les fichiers incompatibles restent protégés.

On peut sauvegarder un conflit **avant** l'entrée dans le RTS et **après** son résultat.
La reprise exacte d'une bataille tactique en cours, avec positions et projectiles,
n'est pas implémentée : F5/F9 sont interceptés dans le RTS et l'écriture d'un
engagement déjà endommagé est refusée. Fermer la fenêtre ne sauvegarde pas automatiquement.

Les rapports des vingt derniers engagements sont conservés dans le JSON ; le bouton
galactique ouvre le dernier rapport. Les croiseurs de ce rapport sont paginés.

## Ressources graphiques

Aucun sprite de vaisseau n'a été trouvé dans les sources actives. Les trois classes
utilisent des formes vectorielles distinctes, avec couleur de faction, sélection
lumineuse et barres de coque/bouclier. Le chargement facultatif de `fighter.png`,
`corvette.png` et `cruiser.png` est prévu dans `assets/ships/`. Aucun asset n'a été
téléchargé, généré ou supprimé.

## Commandes RTS

| Entrée | Action |
|---|---|
| Clic gauche / rectangle | Sélectionner ses unités |
| Maj + clic | Ajouter / retirer une unité |
| Maj + rectangle | Ajouter à la sélection |
| Clic droit au sol | Déplacement en formation |
| Clic droit sur un ennemi | Concentration des tirs sur la cible |
| A puis clic gauche | Attaque-déplacement |
| S bref | Arrêt, au relâchement de la touche |
| S maintenu au moins 180 ms | Déplacer la caméra vers le bas, sans ordre d'arrêt |
| Z / Q / D | Caméra vers le haut / gauche / droite |
| Flèches | Caméra, sans conflit avec la touche d'arrêt |
| H | Tenir la position, tir automatique à portée |
| Ctrl + 1–9 | Mémoriser un groupe |
| 1–9 | Rappeler un groupe, sans changer la vitesse galactique |
| Molette / glisser milieu | Zoom / déplacement de caméra |
| Espace | Pause tactique |
| Échap | Menu tactique : reprendre ou se replier |

La distinction S bref / S maintenu permet de conserver à la fois ZQSD et S pour
l'arrêt. Les contrôles galactiques ne sont pas exécutés dans la scène de bataille.

## Performance et précautions

- Pygame reste lancé uniquement à la demande de l'utilisateur, dans la fenêtre
  logicielle existante limitée à 30 images/s, sans demande OpenGL ni audio.
- La logique tactique avance à pas fixe de 1/30 s avec six pas au plus par appel.
- Décisions IA toutes les 0,35 s ; acquisition de cibles échelonnée et recherches
  locales par grille spatiale. Les unités lointaines ne sont pas toutes interrogées
  à chaque image ; une recherche globale peut choisir un objectif lors d'une décision IA.
- Quarante-huit unités actives par camp, soit 96 actives au plus. Les autres vaisseaux
  restent en réserve, puis sont déployés après les pertes sans recréer un UID détruit.
- Au plus 256 projectiles et 100 effets ; caches graphiques et rotations bornés.
- Campagne gelée pendant le combat ; économie toujours désactivée.
- Aucun benchmark graphique ni certification de stabilité Windows réalisé.

## Tests réellement exécutés

**38 tests de logique réussis, zéro échec et zéro erreur**, dans un seul processus
Python 3.12.14. Dernière durée enregistrée : environ 0,13 s. Aucun import de Pygame,
affichage, audio ou navigateur. Preuve : `LOGIC_TESTS_0_2.json`.

| Demande de validation | Résultat et méthode |
|---|---|
| Dégâts de bouclier et coque | OK : absorption, débordement, destruction et refus des valeurs non finies |
| Tir réel | OK : projectiles simulés causant une baisse de coque/bouclier |
| Combat complet | OK : deux flottes de huit unités se battent jusqu'au résultat par les tirs réels |
| Victoire et conquête | OK : combat tactique puis application du résultat au propriétaire du système |
| Identifiants / survivants | OK : objets originaux, UID uniques, pertes retirées et dégâts conservés |
| Aucun doublon au retour | OK : double application du résultat sans nouvel objet ni second rapport |
| IA/IA | OK : résolution automatique déclenchée à l'arrivée et reproductibilité par graine |
| Retraite et captures | OK : trajet vers refuge et suppression des capturés sans les compter comme détruits |
| Limite et réserves | OK : 120 participants, 96 actifs, déploiement après trois pertes et aucun retour des morts |
| Sauvegarde après combat | OK : écriture et relecture réelles de fichiers temporaires, flottes vides incluses |
| Anciennes sauvegardes | OK : format 1 migré sans récompense ni modification des flottes |
| Trajets et ancienne carte | OK : 15 systèmes, 26 routes, occupation neutre, IA et fraction de pas conservées |
| Commandes | OK logique : événements factices pour groupes, Échap, S/H, séparation des vitesses et blocage F5/F9 |
| Astéroïdes et formations | OK logique : exclusion géométrique, positions de formation et mission attaque-déplacement conservée |
| Scènes Pygame et sprites | NON TESTÉ graphiquement : vérification statique uniquement |

L'analyse statique couvre le point d'entrée, les sources, les outils et les tests :
syntaxe Python 3.11, imports et symboles locaux, séparation domaine/rendu,
dépendances, versions et configurations VS Code. Résultat dans `PYTHON_STATIC_CHECKS.json`.

Un premier processus de tests a été arrêté lorsqu'un accès aux temporaires du
sandbox restait bloqué. La suite finale utilise des répertoires temporaires sous
`tests/` et une exécution Windows autorisée, en un seul processus léger. Aucun
test graphique n'a été lancé pour contourner ce problème.

## Fichiers créés

- `src/star_arena/domain/ship_stats.py`
- `src/star_arena/systems/tactical.py`
- `src/star_arena/systems/spatial.py`
- `src/star_arena/systems/formations.py`
- `src/star_arena/presentation/battle_input.py`
- `src/star_arena/presentation/battle_renderer.py`
- `tests/test_warfare.py`
- `tools/run_logic_tests.py`
- `assets/ships/README.md`
- `docs/ETAT_PROJET_PYTHON_0_2.md`, `docs/LOGIC_TESTS_0_2.json`

## Fichiers modifiés

- `src/star_arena/domain/models.py`, `systems/combat.py`, `systems/simulation.py`
- `src/star_arena/persistence.py`, `app.py`, `config.py`, `__init__.py`
- `src/star_arena/presentation/renderer.py`, `presentation/camera.py`
- `pyproject.toml`, `tools/check_static.py`, `AGENTS.md`, `README.md`
- `docs/ETAT_PROJET_PYTHON.md` : lien vers le nouvel état ; ancien rapport préservé
- `docs/PYTHON_STATIC_CHECKS.json` : résultat du contrôle statique actualisé

## Limites et fonctionnalités non développées

- Rendu, clics réels, zoom, placement des panneaux et chargement de PNG à vérifier manuellement.
- Contournement local, sans recherche de chemin globale : des détours peu efficaces
  ou des encombrements restent possibles et doivent être observés en jeu.
- Pas de sauvegarde tactique au milieu d'un engagement ni de simulation simultanée
  de plusieurs batailles observées. Les renforts en transit restent figés avec la campagne.
- Pas de vaisseaux de remplacement, production, réparation, ressources ou bâtiments.
- Pas d'amiraux, doctrines, sièges, diplomatie, multijoueur, audio ou export Web.
- La suppression de tous les vaisseaux d'une faction n'affiche pas encore un écran
  de fin de campagne. Les données et rapports restent consultables.
- Aucun défaut de logique reproduit ne reste ouvert dans les 38 tests ; cela ne
  vaut pas validation générale de la V0.2 ni preuve d'absence de bug visuel.

## Validation manuelle à effectuer par l'utilisateur

1. Lancer la commande ci-dessous, choisir une faction et démarrer une campagne.
2. Confirmer la présence des 15 systèmes et des trois flottes.
3. Effectuer plusieurs trajets, puis viser un système voisin contenant une flotte
   ennemie. S'il est vide à l'arrivée, son occupation directe est normale.
4. Ouvrir le RTS depuis le panneau de conflit ; essayer sélection, rectangle, Maj,
   déplacements, attaque ciblée, A, S bref, H, formations et groupes Ctrl+1–9.
5. Vérifier ZQSD, S maintenu, flèches, zoom, pause et menu Échap.
6. Terminer la bataille ou se replier ; lire le rapport et revenir à la galaxie.
7. Sauvegarder avec F5, recharger avec F9 et comparer territoire, composition et dégâts.

```powershell
# Lancement graphique : uniquement à l'initiative de l'utilisateur
.\.venv\Scripts\python.exe main.py

# Contrôles sans fenêtre
.\.venv\Scripts\python.exe tools\check_static.py --report
.\.venv\Scripts\python.exe -B tools\run_logic_tests.py --report
```
