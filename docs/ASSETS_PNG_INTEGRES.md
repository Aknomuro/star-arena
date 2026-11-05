# Assets PNG intégrés — 5 novembre 2026

Les neuf sprites ci-dessous sont désormais présents dans le projet et sélectionnés
en priorité par le rendu RTS. Ils proviennent du dossier indiqué par l'utilisateur :

`STAR_ARENA_V9_Tactical_Fleet/STAR_ARENA/assets/ships/` (chemin de provenance relatif, sans données personnelles).

Le pack comporte vingt PNG. Seuls les neuf nécessaires aux trois factions et aux
trois classes actuelles ont été copiés. Les originaux ne sont ni déplacés ni modifiés.

## Correspondances exactes

Chemins de destination relatifs à `assets/ships/` :

| Faction du jeu Python | Classe actuelle | PNG source V9 | Destination |
|---|---|---|---|
| République stellaire | Chasseur | `chasseur.png` | `republic/fighter.png` |
| République stellaire | Corvette | `corvette.png` | `republic/corvette.png` |
| République stellaire | Croiseur | `croiseur_lourd.png` | `republic/cruiser.png` |
| Empire galactique | Chasseur | `tie_interceptor.png` | `empire/fighter.png` |
| Empire galactique | Corvette | `nebulon_b.png` | `empire/corvette.png` |
| Empire galactique | Croiseur | `imperial_star_destroyer.png` | `empire/cruiser.png` |
| Alliance des mondes | Chasseur | `x_wing.png` | `alliance/fighter.png` |
| Alliance des mondes | Corvette | `tantive_iv.png` | `alliance/corvette.png` |
| Alliance des mondes | Croiseur | `mc80_liberty.png` | `alliance/cruiser.png` |

Les classes d'origine ont été relevées dans `sprites.py` et `settings.py` de la V9,
sans exécuter ces fichiers. Le TIE Interceptor est classé Intercepteur dans la V9,
le MC80 Liberty Croiseur léger ; ils représentent ici le chasseur et le croiseur
existants, avec **les statistiques Python inchangées**.

La V9 emploie deux équipes et ne définit pas les trois factions de la reconstruction.
Les affectations ci-dessus sont donc des affectations visuelles locales, pas des
métadonnées de faction natives du pack. Le Nebulon-B fournit la troisième silhouette
de corvette. Les couleurs originales des PNG sont conservées ; les marqueurs de
faction de l'interface continuent d'identifier les camps. Aucune recoloration n'a été faite.

## Intégration technique

- Neuf PNG réels, tous **256 × 256**, avec canal alpha déclaré dans leur en-tête RGBA.
- Copie binaire identique : SHA-256 source/destination comparés pour chacun des neuf fichiers.
- `assets/ships/manifest.json` enregistre source, classe, destination, orientation
  et empreinte de chaque fichier, sans importer du code de la V9.
- Les images pointent vers le haut. Le catalogue applique un décalage natif de
  −90° à l'affichage afin de suivre le cap du moteur. Les PNG eux-mêmes restent inchangés.
- Redimensionnement avec conservation du ratio et tailles de classe 42 / 72 / 112
  unités, adaptées au zoom. Les hitboxes restent inchangées.
- Rotation lissée à pas d'un demi-degré, originaux et transformations mis en cache
  avec les limites existantes.
- En cas de fichier manquant ou illisible, essai du générique puis secours vectoriel.
- Aucune dépendance au dossier Downloads pendant le jeu : les copies locales suffisent.

## Autres PNG du pack non activés

`a_wing.png`, `assault_frigate.png`, `b_wing.png`, `bombardier.png`,
`croiseur_leger.png`, `e_wing.png`, `eclaireur.png`, `home_one.png`,
`intercepteur.png`, `victory_destroyer.png`, `y_wing.png`.

Ils restent dans le dossier source. Ils représentent des variantes ou des classes
supplémentaires ; aucune nouvelle unité ni règle n'a été introduite pour les utiliser.
Aucun sprite ne manque parmi les neuf emplacements retenus pour le jeu actuel.

## Vérifications réellement effectuées

- Inventaire et inspection statique des neuf images et de leur orientation.
- Contrôle des neuf en-têtes PNG, dimensions, canal alpha déclaré et empreintes.
- Neuf emplacements dédiés reconnus, zéro manquant, aucune erreur de manifeste.
- Analyse statique de **30 fichiers Python**, sans erreur détectée ; aucun import
  de Pygame, lancement du jeu ou test graphique.

Preuves actualisées : `SHIP_ASSETS_0_2_1.json` et `PYTHON_STATIC_CHECKS.json`.
Les 64 tests de logique de la V0.2.1 sont un résultat antérieur : ils n'ont pas été
réexécutés pour cette intégration limitée aux assets et à l'orientation de rendu.
L'affichage réel, la rotation dans Pygame et l'apparence au zoom restent à confirmer
lors d'un lancement manuel par l'utilisateur.

## Fichiers concernés

- Ajout : les neuf PNG listés, `assets/ships/manifest.json` et ce rapport.
- Modification : `presentation/fleet_assets.py`, `presentation/ship_sprites.py`,
  `tools/audit_ship_assets.py` et la documentation graphique.
- Combat, statistiques, sauvegardes et commandes : aucun fichier modifié.
