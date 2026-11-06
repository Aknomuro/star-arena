# Correctif écran noir Web — V0.4.1

## Analyse des vrais fichiers publiés

Le 6 novembre 2026, le HTML et `arena.apk` de `https://aknomuro.github.io/star-arena/`
ont été lus par HTTP sans lancer de navigateur sur le PC. Réponses HTTP 200 ; archive de
1 074 001 octets avec 58 fichiers, dont `assets/main.py`, `assets/src/star_arena/app.py`,
neuf PNG et six WAV. Les fichiers du jeu étaient donc présents. Cela ne prouve pas leur exécution.

Le chargeur Pygbag 0.9 utilise `shell.preload_code` avant d'exécuter le code de `main.py`.
Le paquet dans `src/` n'était pas directement importable pendant cette étape, alors que
`main.py` contenait déjà `from star_arena.app import run_game`. C'est une fragilité démontrée
de l'empaquetage ; son rôle exact dans l'écran noir doit être confronté au test navigateur.

Un préchargement HTML optionnel vers `pythonrc.py` renvoie 404 sur le CDN ; le véritable
chargeur est `cpythonrc.py`, accessible. Cette URL de préchargement ne doit pas être confondue
avec une preuve que tout le runtime est absent.

## Corrections

- L'archive Web place désormais `star_arena/` directement à côté de `main.py`. Le projet PC
  conserve `src/star_arena/`. `project_root()` résout correctement PNG, WAV et pont JS dans les deux dispositions.
- L'import du jeu se fait dans la coroutine `bootstrap`, après préparation du chemin et des
  diagnostics. Les exceptions d'import, d'initialisation et de boucle remontent au rapport visible.
- Le point d'entrée accepte le contexte d'exécution Emscripten et conserve le lancement PC.
- Les étapes Python, imports, Pygame, display et premier menu sont journalisées. Un premier
  dessin du menu est effectué avant de traiter la perte éventuelle de focus.
- Le Web utilise explicitement la police Pygame par défaut, sans recherche des polices système Windows.
- `web/boot.js` est inséré avant le runtime dans le HTML généré, indépendamment de `web/browser.js`.
  Il affiche chargement, attente et erreurs JS/Python/WASM sans masquer durablement le canvas.
  L'overlay disparaît seulement au signal envoyé après le premier dessin du menu.
- Le vérificateur du build contrôle les membres et octets de l'archive, compile les sources
  Python sans les exécuter et vérifie l'ordre du script de diagnostic avec `--startup`.

Le workflow manuel construit puis teste le démarrage sous `/star-arena/` dans Chromium headless
sur le runner GitHub. Il bloque le déploiement si le menu n'est pas confirmé et conserve
`console.json`, `result.json` et `menu.png` dans l'artefact `web-startup-diagnostics`.
Le script de ce test refuse de fonctionner hors d'un runner marqué `GITHUB_ACTIONS=true`.
Aucun Pygbag, navigateur ou logiciel n'est installé/lancé automatiquement sur le PC.

## Vérifications locales

234 tests légers réussis dans un seul processus, aucun import Pygame et aucune fenêtre.
Les tests supplémentaires couvrent paquet plat, racines d'assets PC/Web, bootstrap simulé,
exception d'import visible, ordre des diagnostics et interdiction du test graphique hors CI.
Contrôle statique : 68 fichiers Python sans erreur. Syntaxe des deux scripts JS vérifiée par Node.

Une première exécution a rencontré un refus Windows transitoire de remplacement d'un fichier
temporaire de test de migration. Une nouvelle exécution complète a réussi, sans changement des
règles de sauvegarde ni accès aux sauvegardes utilisateur. Le rapport final ne contient pas de trace privée.

## Test navigateur distant et limites

État au moment de la préparation de ce commit : test CI à exécuter. Un build réussi ne sera pas
présenté comme une validation du navigateur. Les résultats effectifs seront précisés après le run.
Même un premier menu vérifié dans Chromium ne valide pas l'ensemble du gameplay, des codecs audio,
du stockage et des interactions, ni une session complète dans Chrome ou Edge sur votre PC.

## Relancer et diagnostiquer

1. Dépôt GitHub → **Actions → STAR ARENA Web Edition → Run workflow**, branche `main`.
2. Attendre les étapes de build, vérification de l'archive et test Chromium, puis `deploy`.
3. Si échec, télécharger `web-startup-diagnostics` dans le résumé du run ; lire `result.json`
   et `console.json`, et regarder `menu.png` si disponible.
4. Après succès, ouvrir le site et actualiser avec Ctrl+F5. Cliquer si Pygbag attend le geste utilisateur.
5. Si le menu manque encore, relever le message STAR ARENA affiché et F12 → Console.

Fichiers : `main.py`, résolution d'assets dans `config.py`, `web.py`, `presentation/music.py`
et `battle_renderer.py`, initialisation dans `app.py` et `renderer.py`, outils de staging/build,
`web/boot.js`, test Chromium réservé CI, workflow et tests de logique associés. Les sauvegardes,
assets source, règles de jeu, serveur LAN et données personnelles sont préservés.
