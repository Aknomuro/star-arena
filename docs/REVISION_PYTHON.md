# Révision du projet Python — 4 novembre 2026

Périmètre : tous les fichiers Python du projet actif, ses dépendances et ses
configurations VS Code. Les anciens projets Godot n'ont pas été modifiés pendant
cette révision. Aucun serveur MCP, jeu, navigateur ni test graphique lancé.

## Corrections issues de la lecture du code

- **Faction après reprise** : changer le choix du menu puis reprendre pouvait
  laisser une autre faction dans le filtre de sélection. La sélection consulte
  maintenant la faction de la campagne ; la reprise resynchronise le choix du menu.
- **Changements d'écran** : les anciennes zones de clic sont invalidées immédiatement.
  La fermeture arrête aussi le traitement des événements restants.
- **Déplacements** : le bouton et les ordres utilisent le même validateur ; le
  bouton n'ignore plus la présence éventuelle d'une flotte hostile.
- **Flottes nombreuses** : la liste affiche la page de la flotte sélectionnée et
  propose une navigation, au lieu de limiter les boutons aux deux premières flottes.
- **Horloge** : tolérance sur le calcul des pas, nombre de pas par image borné et
  horloge arrondie pour limiter la dérive des intervalles. La fraction de pas est
  conservée dans les sauvegardes ; les sauvegardes précédentes restent lisibles.
- **État chargé** : vérification des capitales, des flottes immobiles et des caractères
  de contrôle ; booléens exclus des nombres et identifiants, données JSON ambiguës
  ou non finies refusées.
- **Écriture** : fichier temporaire unique dans le dossier cible, synchronisation
  puis remplacement atomique. Le lecteur borne réellement les octets lus ; le
  rédacteur vérifie aussi la taille. Un fichier existant incompatible reste protégé.
- **Installation en paquet** : le chemin de sauvegarde ne pointe plus dans les
  bibliothèques Python. Le lancement depuis les sources conserve `saves/campaign.json`.
- **Entrées et affichage** : la simulation et le rendu s'arrêtent en arrière-plan.
  La pause manuelle reste indépendante de la perte du focus.

Ces problèmes et risques ont été identifiés par lecture ; ils n'ont pas été reproduits
en exécutant le jeu, conformément à la contrainte de vérification statique.

## Optimisations appliquées

- Cache LRU des surfaces de texte, limité à 256 entrées et deux millions de pixels.
- Recherche dichotomique pour raccourcir les textes, avec place réservée à l'ellipse.
- Coordonnées des systèmes calculées une seule fois par image et omission des
  systèmes et flottes éloignés de la zone visible.
- Position de souris lue une fois par rendu pour les boutons ; sélection des
  systèmes par distances au carré, sans créer de vecteur pour chaque candidat.
- Pas de rendu en arrière-plan, boucle d'événements limitée à 10 Hz dans ce cas.
- Indexation automatique Pylance désactivée et diagnostics limités aux fichiers
  ouverts ; les contrôles statiques du projet complet restent disponibles séparément.
- Numéro de version partagé par le menu et le titre de fenêtre.

Aucun gain de FPS, consommation mémoire ou résultat de stabilité Windows n'est
affirmé : aucune mesure d'exécution n'a été réalisée.

## Validation réellement exécutée

`tools/check_static.py --report`, avec le Python privé de Codex en mode isolé
`-I -B`. Le script n'importe ni Pygame ni le jeu. Il vérifie la syntaxe compatible
Python 3.11, l'existence des modules et des symboles locaux importés, la séparation
simulation/rendu, les dépendances, les versions et les configurations VS Code.
Les résultats et la liste exacte des fichiers sont dans `PYTHON_STATIC_CHECKS.json`.

Ce contrôle ne remplace pas un analyseur de types complet ni des tests fonctionnels.
Le lancement manuel, les interactions, les sauvegardes en conditions réelles et
les performances restent **NON TESTÉS**.

## Fichiers modifiés

`main.py`, `src/star_arena/app.py`, `config.py`, `domain/galaxy.py`,
`domain/models.py`, `systems/simulation.py`, `persistence.py`,
`presentation/renderer.py`, `tools/check_static.py`, `.vscode/settings.json`,
`README.md`, `docs/PYTHON_STATIC_CHECKS.json` et ce rapport.

Les batailles RTS et l'économie restent des extensions futures, sans changement
de périmètre lors de cette révision.
