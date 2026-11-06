# STAR ARENA — V0.4.1 : Web Edition & GitHub Pages

Rapport initial de préparation conservé. Depuis le correctif du 6 novembre 2026, le build,
le menu et une interaction ont été vérifiés dans Chromium distant et déployés sur Pages.
Voir [WEB_STARTUP_FIX_0_4_1.md](WEB_STARTUP_FIX_0_4_1.md) pour l'état actuel et les preuves.

## État de livraison

L'adaptation solo Web est implémentée dans le moteur existant. Le paquet source/assets est
réellement préparé dans `web_build/arena/` : **58 fichiers, 1 286 187 octets**. Son inventaire
avec chemins, tailles et SHA-256 est dans `docs/WEB_PACKAGE_0_4_1.json`.

**Aucun build Pygbag, déploiement GitHub Pages ou test dans un navigateur n'a été exécuté.**
Pygbag est absent du Python de vérification utilisé. Conformément aux précautions demandées,
aucune dépendance n'a été installée et aucun téléchargement de runtime WASM, jeu, fenêtre,
navigateur, son réel ou serveur Web permanent n'a été lancé. Cette version n'est donc pas
déclarée jouable ou stable dans Chrome/Edge. Le staging ne contient pas encore `index.html`
et le runtime compilé : ce sont les sorties du build manuel ou du workflow fourni.

## Audit et adaptations

| Élément | Adaptation / compatibilité prévue | Validation réelle |
| --- | --- | --- |
| Moteur solo | Même simulation Python, économie, flottes, navigation, planètes, stations, milices, conquêtes et RTS. Pas de moteur Web dupliqué. | Régressions de logique réussies. |
| Boucle Pygame CE | Coroutine existante conservée ; `await asyncio.sleep(0)` à chaque itération, `Clock.tick(0)` sur Web, aucune attente de cadence bloquante. | Inspection et tests sans Pygame. |
| Entrée `main.py` | `asyncio.run(run_game())` ; `SystemExit` uniquement sur desktop, pour ne pas interrompre la programmation asynchrone du runtime Web. | Test statique et tests de routage. |
| Cadence | Rendu Web limité par temps accumulé à 30 images/s, tout en rendant la main au navigateur à chaque itération. | Logique inspectée ; cadence réelle non mesurée. |
| Réseau | Chargement du contrôleur LAN uniquement sur desktop. Adaptateur Web inactif, bouton « Multijoueur Web en préparation ». Serveur, client et protocole LAN non empaquetés. | Import desktop interdit dans le test de construction de l'application Web. |
| Persistance | `BrowserStore` utilise `localStorage` via un pont JS ; aucun chemin Windows ou fichier de campagne PC utilisé sur Web. | Pont simulé : sauvegarde, chargement et erreurs testés. API DOM réelle non testée. |
| Audio | Mixer facultatif, activation après geste ; musique et effets restent séparés. Les erreurs sont visibles dans l'interface et la barre Web. | Tests de logique et backends simulés ; codecs et audio navigateur non testés. |
| Dépendances | Jeu : Pygame CE et stdlib. Build : `pygbag==0.9.2`, Python WASM 3.12 explicitement choisi. | Version/options vérifiées dans les sources officielles ; aucune installation locale. |
| Interface | Canvas logique 1280×800, affichage CSS proportionnel selon la fenêtre ; barre DOM pour sauvegarde, import/export, audio, qualité, admin solo et plein écran. | Syntaxe JS contrôlée ; clics, coordonnées SDL et plein écran à tester en navigateur. |
| Pages | Workflow manuel, archive et ressources relatives, contrôle des références HTML à la racine, `.nojekyll` généré après vérification. | Structure préparée ; aucune exécution GitHub Actions. |

Les dépendances stdlib de la simulation ont été conservées ; aucune dépendance binaire additionnelle
n'a été introduite. Les opérations fichier de `persistence.py` restent utilisées sur PC, tandis que
le Web réutilise seulement la validation et la sérialisation. Les chemins des assets sont calculés
depuis le paquet, sans dépendre du dossier Windows de lancement. Une indisponibilité du pont Web
ne déclenche pas de repli vers une sauvegarde dans un système de fichiers volatil.

Le runtime Pygbag et ses composants sont fournis depuis un CDN HTTPS. Le code local est déterminé
par la version du dépôt et le packager est fixé ; les téléchargements externes restent nécessaires
au build/chargement. L'application n'est pas présentée comme autonome hors ligne.

## Sauvegardes navigateur

- **Nouvelle campagne** utilise le même moteur et ne remplace pas automatiquement le stockage.
- **Sauver** valide et sérialise la campagne au format JSON 5 existant, maximum 2 000 000 octets.
  L'écriture utilise `localStorage.setItem`, et son échec laisse la valeur précédente en place.
- **Charger** valide complètement le JSON avant de remplacer la simulation active.
- **Exporter JSON** télécharge la campagne en mémoire via un Blob navigateur ; reste disponible
  lorsque le stockage local est bloqué. Le jeu demande le téléchargement, sans garantir que le
  navigateur ou ses réglages l'autorisent : vérifier le fichier reçu.
- **Importer JSON** ouvre un sélecteur de fichier. La taille et le contenu sont vérifiés avant
  remplacement de la campagne active. L'import ne sauvegarde pas automatiquement : cliquer Sauver.
- Les opérations sont refusées pendant le RTS actif afin de ne pas sérialiser une campagne
  intermédiaire qui ignorerait les pertes en cours. Terminer la bataille avant ces opérations.

Le stockage est séparé par origine et chemin de site, avec un préfixe `star-arena:v1:`. La campagne
et les préférences audio ont des clés distinctes. Si une valeur existante est corrompue ou sa
version incompatible, elle n'est pas écrasée silencieusement. Une modification déjà visible depuis
un autre onglet est détectée par comparaison avec la valeur lue : exporter la campagne courante
avant de recharger pour choisir la version à conserver. Cela ne constitue pas une synchronisation
temps réel entre onglets ; éviter de jouer la même sauvegarde simultanément dans plusieurs onglets.

Quotas, stockage refusé et JSON invalides produisent des messages. Navigation privée, nettoyage
du navigateur, changement de domaine ou de chemin peuvent empêcher de retrouver la sauvegarde.
L'export JSON régulier reste la copie transportable recommandée. Les données du PC ne sont pas
automatiquement accessibles au site et aucun fichier de sauvegarde privé n'est livré avec le jeu.

## Assets réellement inclus

| Faction | PNG inclus |
| --- | --- |
| République | `assets/ships/republic/fighter.png`, `corvette.png`, `cruiser.png` |
| Empire | `assets/ships/empire/fighter.png`, `corvette.png`, `cruiser.png` |
| Alliance | `assets/ships/alliance/fighter.png`, `corvette.png`, `cruiser.png` |

Les neuf fichiers originaux sont copiés sans conversion. Le manifeste Web conserve l'affectation,
l'orientation et les empreintes, mais retire le chemin local Windows de provenance. Le manifeste
source du projet reste intact. Le secours vectoriel, les proportions et les caches de sprites sont
conservés. Les éléments de fond et de planètes sont dessinés par le code embarqué.

Six musiques existantes incluses : `assets/audio/music/main_menu.wav`, `galaxy.wav`, `planetary.wav`,
`battle.wav`, `victory.wav`, `defeat.wav`. Les six fichiers `.ogg` historiques envisagés sont absents ;
les WAV servent de pistes disponibles. Les sept effets (clic, ordre, laser, impact, bouclier,
explosion, confirmation) sont synthétisés par `presentation/audio.py`, inclus dans le paquet ;
aucun fichier d'effet externe fictif n'a été créé.

## Optimisation et interface

La projection des systèmes et la surface des routes neutres sont conservées tant que la caméra
et la géométrie ne changent pas. Les routes d'itinéraire ou de sélection sont superposées. Ce cache
ne dépend pas des ressources ou du temps de simulation et n'est pas recalculé à chaque frame.
Une seule projection et une seule surface de routes sont retenues. Zoom ou déplacement invalident
le cache. La minimap, les textes, panneaux, halos, planètes, échelles et rotations conservent leurs
caches bornés existants. Le profil réduit, choisi sur Web par défaut, conserve les plafonds
d'effets et de débris ; F7 et le bouton Qualité permettent de changer le profil. Les règles,
statistiques, fréquence des décisions IA et pas de simulation n'ont pas été changés.

Le canvas garde son ratio ; aucun redimensionnement des images source n'est effectué à chaque
frame. Le redimensionnement CSS adapte tout le rendu, boutons compris. Il vise les ordinateurs,
sans nouvelle interface mobile imposée. La molette et le clic droit sur le canvas empêchent le
défilement/menu contextuel de page. Les touches du jeu sont capturées lorsque le canvas a le focus.
Cliquer dans le jeu après un bouton DOM lui rend le focus. Le plein écran est demandé directement
par un clic utilisateur et affiche une erreur si refusé ou indisponible.

## Build et publication

Procédure complète et commandes exactes : [web/README.md](../web/README.md).

Publication recommandée sans compilation locale :

1. Envoyer les sources nécessaires et ce workflow dans votre propre dépôt GitHub. Vérifier les
   fichiers avant commit ; ne pas envoyer `.venv`, `.venv-web`, `saves`, `settings`, anciens dossiers
   et archives par inadvertance. Aucun dépôt n'a été créé ou connecté automatiquement ici.
2. Ouvrir **Settings → Pages → Build and deployment → Source : GitHub Actions**.
3. Ouvrir **Actions → STAR ARENA Web Edition → Run workflow** sur la branche de la V0.4.1.
4. Attendre `build` : préparation isolée, installation du packager sur le runner, Pygbag `--build
   --no_opt --PYBUILD 3.12`, contrôle de `index.html` et de l'archive, ajout de `.nojekyll`.
5. Attendre `deploy`, puis utiliser l'URL réellement renvoyée par GitHub, sans supposer de nom
   d'utilisateur ou de dépôt. Vérifier le site sous son vrai chemin de projet avant de partager.

Seul `web_build/arena/build/web` est publié. Le vérificateur compare les membres et octets de
l'archive à la liste autorisée : fichiers inattendus, manquants, dupliqués et données privées sont
refusés. Il contrôle les références HTML à la racine, incompatibles avec un sous-chemin de dépôt.
Ce contrôle ne remplace pas le chargement réel du runtime et de l'archive sous `/star-arena/`.
Le workflow est uniquement manuel ; aucun push ni publication n'a été réalisé pendant ce travail.

## Tests exécutés et limites

| Contrôle | Statut | Méthode |
| --- | --- | --- |
| Régressions PC/solo et LAN | OK | 198 tests existants conservés, dont vrais échanges de test sur 127.0.0.1 ; aucune socket LAN ouverte automatiquement. |
| Logique Web | OK | 22 nouveaux tests : stockage, quotas simulés, conflits d'onglets, JSON, import/export, garde RTS, activation audio, routage sans fichiers PC ni serveur LAN, paquet et projection. |
| Suite totale | OK | **220 tests**, 0 erreur, 0 échec, 0 ignoré ; Python 3.12.14, un seul processus, sans import Pygame. Rapport `docs/LOGIC_TESTS_0_4_1.json`. |
| Analyse statique | OK | 63 fichiers Python, 212 imports locaux, 423 symboles, aucune erreur ; `docs/PYTHON_STATIC_CHECKS.json`. |
| Syntaxe JavaScript | OK | `node --check web/browser.js`, aucune erreur. Aucun DOM exécuté. |
| Staging réel | OK | Copie des 58 fichiers autorisés ; neuf PNG, six WAV et code des sept effets ; tailles, casse et empreintes inventoriées. |
| Vérificateur d'archive | OK | Tests sur une archive fixture synthétique, y compris rejet de données privées et de chemins racine. La fixture n'est pas un build WASM. |
| Build Pygbag et workflow Pages | NON TESTÉ | Packager non installé dans le Python utilisé ; aucun téléchargement/CI déclenché. |
| Exécution Web, codecs, DOM/JS-Python | NON TESTÉ | Aucun navigateur ni audio réel lancé. |
| Résolution, plein écran, coordonnées, performances | NON TESTÉ | À mesurer sur le site réel dans Chrome et Edge. |
| Multijoueur navigateur / WebRTC | ABSENT | Adaptateur inactif et bouton explicite ; PC/LAN conservé. |

## Test manuel Chrome / Edge

Après le build CI ou le build local décrit dans `web/README.md` :

1. Ouvrir le lien HTTPS Pages réel, cliquer au démarrage Pygbag puis dans le jeu. Vérifier les
   chargements et l'absence de 404 dans les outils développeur, surtout sous le chemin de dépôt.
2. Créer une campagne avec chacune des trois factions ; vérifier la galaxie, les sprites,
   sélection simple/multiple, clic droit, déplacement entre systèmes et zoom sans défilement.
3. Ouvrir une planète, construire et produire ; observer coûts, files et arrivée d'un vaisseau.
4. Jouer une bataille RTS, vérifier tirs, pertes, stations, milices et retour à la carte.
5. Tester les six ambiances, F8, les volumes indépendants, Admin solo, Qualité et perte/reprise du focus.
6. Redimensionner la fenêtre, vérifier boutons/coordonnées, activer Plein écran et sortir avec Échap.
7. Sauver avec déplacement et files en cours ; actualiser puis Charger et comparer données et dégâts.
8. Exporter JSON, importer après une autre campagne puis Sauver. Tester un JSON invalide, stockage
   bloqué et deux onglets : conserver les données existantes et voir un message d'erreur.
9. Répéter dans l'autre navigateur ; leurs stockages sont distincts. Le bouton multijoueur Web doit
   afficher sa préparation et ne doit ouvrir aucun serveur Python.

Si un serveur HTTP local est choisi manuellement, utiliser l'adresse et la commande du guide puis
l'arrêter avec Ctrl+C. Aucun serveur n'est nécessaire sur le PC des joueurs pour utiliser Pages.

## Fichiers concernés

Créés : `src/star_arena/web.py`, `web/browser.js`, `web/.nojekyll`, `requirements-web.txt`,
`.github/workflows/pages.yml`, `tools/check_web_build.py`, `tests/test_web_edition.py`, ce rapport,
`docs/WEB_PACKAGE_0_4_1.json`, `docs/LOGIC_TESTS_0_4_1.json` et la copie isolée `web_build/arena/`.

Modifiés : `main.py`, `src/star_arena/app.py`, `src/star_arena/config.py`,
`src/star_arena/presentation/camera.py`, `src/star_arena/presentation/renderer.py`,
`src/star_arena/__init__.py`, `pyproject.toml`, `tools/prepare_web.py`, `.gitignore`,
`README.md`, `web/README.md`, `AGENTS.md` et `docs/PYTHON_STATIC_CHECKS.json`.

Les modules réseau PC restent présents. Les sauvegardes, mécaniques, statistiques, assets source,
anciens dossiers Godot et archives n'ont pas été supprimés. Aucun PNG ni fichier audio source
n'a été remplacé. Les ajouts Web ne constituent pas une validation graphique de la version PC.

## Références officielles

La boucle à `sleep(0)` et les options de build sont documentées par
[Pygbag 0.9.2](https://pypi.org/project/pygbag/0.9.2/) et ses
[sources du packager](https://github.com/pygame-web/pygbag/blob/0.9.2/src/pygbag/app.py).
L'accès navigateur via `platform.window` est présenté dans les
[exemples officiels Pygbag](https://pygame-web.github.io/wiki/pygbag-code/).
Le stockage et ses cas d'indisponibilité suivent les explications de
[MDN](https://developer.mozilla.org/en-US/docs/Web/API/Web_Storage_API/Using_the_Web_Storage_API).
Les jobs d'artefact et de déploiement suivent la documentation des
[workflows personnalisés GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
