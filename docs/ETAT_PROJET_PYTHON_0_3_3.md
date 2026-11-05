# STAR ARENA Python — V0.3.3

Date : 5 novembre 2026. Polish, ergonomie, carte arrondie, batailles contextuelles et préparation Web.
Version applicative 0.3.3 ; format de campagne JSON 5 conservé, avec champs optionnels d'arrivée.

## Résultat et limites de validation

Le code est intégré au projet existant. **174 tests de logique réussissent**, sans import de
Pygame, fenêtre, navigateur ni lecture sonore. Les méthodes de rendu ont été modifiées et
vérifiées statiquement ; leur qualité visuelle n'a pas été observée à l'écran. Aucun exportateur
n'a été installé ou exécuté, aucun build HTML5 n'a été publié. Les performances Web réelles et
la persistance durable dans un navigateur restent à vérifier/compléter avant une publication.

## Bug de déplacement : cause et correction

Le clic gauche sur un système sélectionnait automatiquement sa première flotte alliée, même
si une autre flotte source était déjà choisie. De plus, les flottes sont dessinées avec un
décalage par rapport au centre du système, mais le clic droit ne visait que ce centre : viser
une icône pouvait manquer la destination. Le clic droit lui-même ne sélectionnait pas une autre
flotte dans le code ; c'est la combinaison de ces comportements qui rendait l'ordre ambigu.

Désormais :

- Clic gauche système : sélection de système uniquement ; la source est conservée.
- Clic gauche icône alliée ou Tab : sélection explicite de flotte.
- Clic droit système **ou icône stationnée** : destination d'ordre, jamais sélection de source.
- Une destination alliée occupée ouvre un choix : déplacement simple, renfort conservé séparément,
  ou fusion à l'arrivée avec une flotte précise. Les cibles de fusion sont paginées.
- Le choix conserve l'identifiant de la source, même si plusieurs flottes se trouvent à destination.
  La simulation attend la confirmation ; Échap annule sans modifier l'ordre.
- La fusion utilise les unités existantes, conserve identifiants/coques/boucliers et sélectionne
  la flotte résultante. Si les flottes sont déjà au même système, elle est immédiate.
- Si la cible de fusion a disparu, changé de propriétaire ou quitté le système, la source arrive
  sans fusion et conserve ses unités. Un message signale cette annulation.
- Les redirections en transit conservent le segment engagé. Les destinations hostiles déclenchent
  les engagements existants ; les ordres de fusion peuvent aussi se terminer après une victoire.

Les intentions d'arrivée sont des champs optionnels du format 5 : `arrival_mode` et `merge_target`.
Une ancienne sauvegarde sans ces champs conserve un ordre de déplacement simple.

## Galaxie arrondie

Les nouvelles campagnes de 15, 30, 60 ou 100 systèmes utilisent une répartition déterministe
dans un disque elliptique. Les trois capitales gardent leurs identifiants historiques et sont
placées sur des secteurs périphériques éloignés. Les autres positions sont choisies avec une
recherche de candidats espacés, calculée uniquement à la génération. La distribution radiale
varie la densité sans imposer de bras spiraux artificiels.

Un arbre couvrant minimal relie tous les systèmes. Des raccourcis de voisinage sont ajoutés
avec limites de degré et refus des croisements propres ; le réseau reste volontairement peu dense
pour conserver des axes et passages stratégiques. À 60 systèmes, les distances entre capitales
sont supérieures à 1 800 unités dans le cas testé. Les générations de même graine sont identiques.

Le chargement ne régénère jamais une carte : anciennes positions, routes, identifiants, voyages
et capitales sont conservés. L'option de génération `layout="legacy"` reste disponible pour les
fixtures historiques ; les anciens tests géométriques l'utilisent explicitement. Les tests de
la nouvelle forme couvrent les quatre tailles par défaut.

La caméra commence par une vue d'ensemble adaptée aux dimensions. Les noms sont allégés à grand
recul, avec priorité aux capitales, chantiers, sélection et survol. Les systèmes riches/importants
ont un marqueur ; neutres et factions gardent leurs couleurs distinctes. La mini-carte montre
la nouvelle forme et le rectangle de vue courant.

## Améliorations visuelles intégrées

- Fond spatial calculé une seule fois : étoiles variées et couches de nébuleuses discrètes.
- Routes anti-aliasées, cercles adoucis avec gfxdraw si disponible ; repli sans erreur si cette
  extension optionnelle manque dans un runtime.
- Planètes vectorielles ombrées, suréchantillonnées localement puis réduites avec smoothscale.
  Aucune surface plein écran n'est multipliée pour cette opération.
- Halos d'influence légers, sélection et survol distincts, marqueurs de capitale et d'importance.
- Panneaux à coins arrondis, alpha léger, bordure et ombre précalculées.
- Conservation des neuf PNG, de leur alpha, du ratio et des différences de taille ; originaux
  préchargés une fois à l'ouverture du premier rendu tactique, caches de tailles/rotations conservés.
- Résumé du trajet, destination et ETA conservés ; menu de choix d'ordre explicite.

La référence The Ostrakon est appliquée uniquement aux principes de lisibilité, sobriété et
hiérarchie décrits dans la demande. Aucun asset, mise en page ou interface de ce jeu n'a été copié,
et aucune ressource externe n'a été téléchargée pour ce rendu. L'aspect final reste à juger manuellement.

## Batailles contextuelles

`systems/battlefield.py` construit une configuration pure Python une seule fois par engagement :

- Planètes réelles du système : identifiant, nom, type, propriétaire, taille liée à la population.
- Positions de fond réparties côté défenseur, adaptées au nombre de planètes.
- Positions des stations et défenses construites autour de leur planète d'origine.
- Placement espacé des installations ; le cas dense de cinq planètes et 25 défenses est testé.
- Astéroïdes reproductibles selon la graine, l'identifiant du système et sa richesse, avec une
  zone dégagée autour des installations.

Le moteur tactique reçoit ces coordonnées et utilise les mêmes objets de station/plateforme
que la campagne. Les unités construites sont prioritaires sur les réserves, dans le plafond
tactique existant. Les milices et flottes restent déployées par le moteur habituel.
Aucune station gratuite n'est créée par le décor.

Les planètes sont des repères d'arrière-plan nommés et typés, avec orbites locales visibles :
elles n'ajoutent pas de collision gigantesque, n'interceptent pas les tirs et ne bloquent pas
les navires. Les défenses restent des unités physiques destructibles, avec ciblage, portée et
état persistants. Les armes, dégâts et statistiques restent inchangés ; le placement de terrain
et des installations peut naturellement modifier la tactique d'une bataille.

## Optimisations et mode qualité réduite

La simulation reste à pas fixe ; économie et production par seconde, décisions militaires à
leur intervalle existant. La recherche de chemin utilise maintenant une adjacency construite
par recherche plutôt qu'un balayage de toutes les routes à chaque voisin. Un planificateur
par simulation garde jusqu'à 128 chemins, invalidés si routes ou positions changent. Les requêtes
répétées de l'interface ne relancent pas Dijkstra. Les chemins bloqués peuvent réutiliser un résultat
négatif en cache jusqu'à changement du graphe.

Le soutien tactique utilise la grille spatiale existante pour trouver ses alliés à portée,
au lieu de comparer chaque installation à toutes les unités. Le déploiement retourne immédiatement
si les réserves sont vides. Les plafonds d'unités et de projectiles restent conservés.

Caches ajoutés/renforcés :

| Cache | Desktop | Qualité réduite |
|---|---:|---:|
| Rotations de sprites | 256 entrées / 4 M pixels | 128 / 1 M pixels |
| Sprites redimensionnés | 64 / 2 M pixels | 32 / 0,5 M pixels |
| Panneaux | 32 / 3 M pixels | 16 / 1,5 M pixels |
| Planètes | 64 / 1 M pixels | 32 / 0,5 M pixels |
| Halos | 32 / 0,5 M pixels | 16 / 0,2 M pixels |
| Texte rendu | 256 / 2 M pixels | 128 / 1 M pixels |

S'ajoutent un cache de mise en lignes de texte borné à 128 entrées et une mini-carte statique
invalide seulement lorsque sa géométrie, ses propriétaires ou ses routes changent. Le cadre de
caméra est superposé, sans reconstruire la carte. Les objets hors champ sont écartés du rendu
avant les transformations principales.

**F7** bascule le profil, également accessible dans les paramètres. En qualité réduite : rotations
par pas de 2° plutôt que 0,5°, tailles regroupées par 4 pixels, 32 effets maximum au lieu de 100,
pas de nouveaux débris et halos secondaires masqués. Les effets déjà présents peuvent finir
leur courte durée de vie ; le rendu est immédiatement limité. La qualité des statistiques de
combat n'est pas modifiée. Les codecs et fichiers audio restent les mêmes.

Ces changements bornent le travail et la mémoire des caches ; aucun benchmark graphique ou
FPS navigateur n'a été effectué. Les nombres ci-dessus sont des budgets de pixels, pas une
mesure de RAM réelle du pilote.

## Préparation Web concrète

La boucle `run_game` est désormais une coroutine asyncio avec cession explicite de la main.
Le lanceur `main.py` et l'entrée desktop restent utilisables. Sur emscripten : qualité réduite
par défaut, cadence coopérative plutôt qu'attente bloquante, initialisation audio différée à
une interaction utilisateur. gfxdraw est optionnel. La sauvegarde native conserve fsync quand
la fonction existe et dispose d'un repli pour les runtimes limités.

`tools/prepare_web.py` audite les fichiers à embarquer et peut préparer manuellement un dossier
isolé avec `--stage web_build`. Aucun exportateur n'est exécuté. Le staging ne supprime rien et
refuse les fichiers existants différents avant de commencer les copies. Le test utilise uniquement
un dossier temporaire, pas un build publié.

Le périmètre audité comprend 53 fichiers, environ **1,26 Mo** de sources et d'assets avant tout
runtime/compression. Il inclut les neuf PNG et six WAV ; archives Godot, .venv, tests, sauvegardes,
préférences et caches sont exclus. Voir `docs/WEB_PREPARATION_0_3_3.json` et `web/README.md`.

Restent nécessaires avant une vraie version Web : choix/validation de l'exportateur et de sa
version, empaquetage des polices/codecs, test des interactions dans le canvas, profilage CPU/RAM,
validation de l'audio après geste utilisateur et persistance durable via un pont navigateur ou
export/import. Les écritures de fichiers dans un système virtuel ne sont pas présentées comme
une sauvegarde durable après fermeture du navigateur. Aucun build HTML5 n'est livré.

## Tests et contrôles exécutés

**174 tests, 0 échec, 0 erreur, 0 ignoré**, Python 3.12.14, environ 1,47 seconde au dernier passage.
156 régressions et 18 tests V0.3.3. Un seul processus léger à la fois ; aucun import de Pygame,
affichage, navigateur ou périphérique audio. Preuve : `docs/LOGIC_TESTS_0_3_3.json`.

| Vérification | Statut | Méthode |
|---|---|---|
| Galaxie arrondie et connectée | OK logique | Quatre tailles, inclusion dans un disque elliptique, ratio largeur/hauteur, parcours du graphe |
| Capitales et identifiants | OK logique | Distances des capitales, unicité des unités/noms, reproductibilité complète |
| Routes lisibles | OK géométrie | Aucune intersection propre entre routes du cas testé |
| Pathfinding multi-étapes | OK logique | Chemin de plusieurs étapes et cache identique sur 100 requêtes |
| Travail/cache de trajectoire borné | OK logique | Une seule recherche pour requêtes répétées, invalidation après retrait de route, éviction au-delà de 128 paires distinctes |
| Clic système sans perte de source | OK entrée simulée | Clic gauche sur système allié occupé conserve la flotte initiale |
| Ordre sur icône de destination | OK entrée simulée | Clic droit sur icône décalée ouvre le choix, source conservée et aucun départ avant confirmation |
| Renfort séparé | OK logique | Arrivée sans fusion ni duplication, composition source et cible conservée |
| Fusion précise et persistante | OK logique | Choix de la flotte parmi plusieurs, sauvegarde/recharge de l'intention, mêmes objets et dégâts après fusion |
| Fusion immédiate | OK logique | Flottes co-localisées fusionnées sans trajet, sélection transférée à la cible |
| Cible de fusion partie | OK logique | Arrivée séparée, unités source et cible intactes |
| Destination vide/hostile et redirection | OK logique | Départ vers neutre, retarget sans saut de position, engagement sur destination ennemie |
| Anciennes sauvegardes | OK logique | Géométrie et données historiques inchangées au rechargement ; régressions de migration conservées |
| Bataille contextuelle | OK logique | Même nombre/IDs de planètes que le système ; génération sans mutation et reproductible |
| Stations et plateformes | OK logique | Objets de campagne identiques dans le moteur, coordonnées autour de la bonne planète, dégagement des astéroïdes |
| Configuration dense | OK logique | Cinq planètes, 25 structures, distances minimales vérifiées entre toutes les paires |
| Qualité réduite | OK logique | Plafond d'effets 32, caractéristiques des unités inchangées, profil de rotation simplifié |
| Cache mémoire | OK logique | Réduction de budget avec éviction et respect du plafond de pixels/entrées |
| Préparation Web | OK préparation | Coroutine détectée, périmètre sans données privées, staging minimal et refus d'écraser un conflit |
| Repli graphique optionnel | OK backend simulé | Primitive sans extension anti-alias, sans création de surface ni erreur |
| Rendu graphique réel | NON TESTÉ | Aucune fenêtre lancée |
| Export HTML5 et performances navigateur | NON TESTÉ | Aucun exportateur installé ni lancé, aucun navigateur ouvert |
| Audio réel | NON TESTÉ | Aucune lecture sonore automatique |

Analyse statique : **51 fichiers Python, 166 imports locaux, 341 symboles, aucune erreur** dans
`docs/PYTHON_STATIC_CHECKS.json`. Les neuf PNG gardent leurs empreintes d'origine. Les tests
existants vérifient encore les six WAV, leur contenu PCM, le mixer simulé et les préférences.

## Fichiers créés ou modifiés

Créés :

- `src/star_arena/domain/galaxy_layout.py` — forme et routes de nouvelle campagne.
- `src/star_arena/systems/battlefield.py` — configuration contextuelle pure Python.
- `src/star_arena/presentation/art.py` — primitives, planètes et panneaux mis en cache.
- `src/star_arena/presentation/quality.py` — profils de présentation.
- `tools/prepare_web.py`, `web/README.md` — périmètre minimal et staging explicite.
- `tests/test_polish_web.py` — 18 tests de cette version.
- `docs/ETAT_PROJET_PYTHON_0_3_3.md`, `docs/WEB_PREPARATION_0_3_3.json`, `docs/LOGIC_TESTS_0_3_3.json`.

Modifiés :

- `main.py`, `src/star_arena/app.py` — boucle coopérative, commandes, choix d'arrivée et F7.
- `src/star_arena/domain/galaxy.py`, `models.py` — génération et intentions d'arrivée.
- `src/star_arena/systems/navigation.py`, `simulation.py` — cache, renfort/fusion et reprise d'ordres.
- `src/star_arena/systems/tactical.py` — environnement, structures, grille de soutien et effets réduits.
- `src/star_arena/persistence.py` — champs d'arrivée optionnels et compatibilité de synchronisation.
- `src/star_arena/presentation/renderer.py` — affichage stratégique, mini-carte et menus.
- `src/star_arena/presentation/battle_renderer.py`, `system_view.py` — planètes et contours.
- `src/star_arena/presentation/ship_sprites.py` — préchargement, regroupement et budgets réduits.
- `src/star_arena/__init__.py`, `pyproject.toml` — version 0.3.3.
- `tests/test_warfare.py`, `test_extremes.py`, `test_expansion.py`, `test_planets.py`,
  `test_navigation_audio_fix.py` — fixtures historiques explicitement conservées.
- `README.md`, `AGENTS.md`, `.gitignore`, `docs/PYTHON_STATIC_CHECKS.json` — documentation et contrôle.

Aucun PNG, WAV, fichier Godot ou archive supprimé ou remplacé. Aucun logiciel ou dépendance installé.

## Vérifications manuelles restantes

1. Nouvelle campagne : observer la forme, les labels aux différents zooms, survol, halos et mini-carte.
2. Sélectionner une flotte source, cliquer un système allié occupé puis donner l'ordre : vérifier
   déplacement, renfort, choix précis de fusion et conservation de la source pendant le choix.
3. Tester le clic droit directement sur une icône, la redirection en vol et la reprise après combat.
4. Attaquer un système fortifié : vérifier planètes, lisibilité des installations autour d'elles,
   collisions ordinaires des navires et persistance des dégâts après résultat.
5. Comparer F7 desktop/réduit : netteté des PNG, transitions, particules et consommation réelle.
6. Vérifier audio et sauvegardes sur desktop, puis effectuer séparément l'export et les contrôles Web
   décrits plus haut avant toute affirmation de compatibilité navigateur complète.

La version n'est pas déclarée stable graphiquement ou validée Web sur la seule base des tests de logique.
