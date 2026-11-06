# Web Edition V0.4.1 — build et publication manuels

Le dossier `web_build/arena/` est une copie source/assets préparée, pas une application HTML5
compilée localement. Aucun Pygbag ni navigateur n'a été lancé sur le PC. Le build et le premier
menu ont depuis été vérifiés sur le runner GitHub ; les parties complètes dans Chrome ou Edge
restent à tester manuellement. Le jeu PC continue de se lancer avec `main.py`.

## Option recommandée : build sur GitHub Actions

1. Créer ou utiliser **votre propre dépôt GitHub**. Envoyer `main.py`, `src/`, les vrais `assets/`,
   `tools/`, `tests/`, `.github/workflows/pages.yml`, `requirements-web.txt`, `requirements.txt`,
   `pyproject.toml`, `.vscode/`, `.gitignore`, `web/` et les documents du projet.
   Vérifier le contenu avant commit : ne pas ajouter les anciens dossiers et archives par mégarde,
   ni les environnements virtuels, sauvegardes et fichiers `settings/` privés.
2. Dans **Settings → Pages**, choisir **GitHub Actions** comme source. Les droits de publication
   dépendent de votre dépôt et des règles éventuelles de votre organisation.
3. Dans **Actions**, sélectionner **STAR ARENA Web Edition**, puis **Run workflow** sur la branche
   contenant la V0.4.1. Le workflow ne se lance pas automatiquement à chaque push.
4. Le job `build` utilise Python 3.12 et `pygbag==0.9.2`, prépare `web_build/arena`, construit avec
   `--build --no_opt --PYBUILD 3.12`, vérifie l'archive et ajoute `.nojekyll`.
5. Le job `deploy` publie uniquement `web_build/arena/build/web`. Consulter l'URL produite par
   GitHub dans ce job ou dans **Settings → Pages**. Tester ce lien avant de le partager.

Les dépendances et le runtime WASM sont téléchargés sur le runner GitHub, pas automatiquement
sur votre PC. GitHub Pages héberge des fichiers statiques ; le serveur WebSocket PC n'y tourne pas.
Les ressources du jeu et son archive utilisent des chemins relatifs, adaptés également à un
chemin de dépôt comme `/star-arena/`. Le runtime Pygbag utilise son CDN HTTPS externe.
Cette version ne promet pas un fonctionnement hors ligne. Aucun dépôt ni lien public n'a été créé.

## Option locale : uniquement si vous décidez de lancer le build

Python **3.12** doit être disponible pour ces commandes. Sinon, utiliser GitHub Actions ou
installer/configurer Python manuellement. Ces commandes n'ont pas été exécutées automatiquement
par Codex. Elles peuvent télécharger des données de runtime.

Depuis la racine du projet, dans PowerShell :

```powershell
py -3.12 -m venv .venv-web
.\.venv-web\Scripts\python.exe -m pip install -r requirements-web.txt
# Conserver l'ancienne copie puis recréer arena depuis les sources actuelles :
.\.venv-web\Scripts\python.exe -B tools/prepare_web.py --stage web_build/arena --refresh --report
.\.venv-web\Scripts\python.exe -B tools/prepare_web.py --verify-stage web_build/arena
.\.venv-web\Scripts\python.exe -m pygbag --build --no_opt --PYBUILD 3.12 --width 1280 --height 800 --ume_block 1 --can_close 1 --package star.arena.web --title "STAR ARENA" web_build/arena
.\.venv-web\Scripts\python.exe -B tools/prepare_web_output.py web_build/arena/build/web
.\.venv-web\Scripts\python.exe -B tools/check_web_build.py web_build/arena/build/web --startup
```

`--refresh` régénère uniquement `web_build/arena`. Sa copie précédente est déplacée intégralement
dans `web_build/stage_history/`, sans suppression de fichiers. Sans cette option, l'outil continue
de refuser les fichiers différents et supplémentaires. `--verify-stage` bloque un staging périmé
ou contenant d'anciens résultats de build avant compilation. Ne pas compiler une vieille copie.
`--no_opt` conserve exactement PNG, WAV et scripts et évite les convertisseurs d'assets externes.
L'archive `.apk` de Pygbag est un ZIP de jeu Web, pas une application Android.

La vérification exige `index.html` et l'archive, compare tous les fichiers autorisés et leur
contenu, refuse les fichiers privés et les références HTML à la racine `/`. Elle ne remplace pas
un test de chargement et d'exécution dans le navigateur.

## Test manuel local dans Chrome ou Edge

Après un build réussi et vérifié, **si vous souhaitez lancer un serveur temporaire** :

```powershell
.\.venv-web\Scripts\python.exe -m http.server 8000 --bind 127.0.0.1 --directory web_build/arena/build/web
```

Ouvrir soi-même `http://127.0.0.1:8000/` dans Chrome ou Edge. Ne pas ouvrir `index.html` en
`file://`. Arrêter le serveur avec **Ctrl+C** après le test. Tester aussi l'URL GitHub Pages
réelle sous son chemin de dépôt : une prévisualisation locale à la racine ne prouve pas tout.

Cliquer pour démarrer Pygbag, puis dans le jeu pour activer le son. Vérifier la carte, les neuf
sprites, la sélection et le clic droit, le zoom sans défilement de page, une planète, un chantier,
un déplacement, une bataille RTS et son retour. Tester Qualité, les volumes, F8 et Admin solo.
Redimensionner la fenêtre et utiliser Plein écran ; revenir par Échap. Cliquer dans le canvas
pour lui redonner le focus clavier après avoir utilisé un bouton de la barre Web.

Sauver, actualiser la page, puis Charger : vérifier positions, dégâts, files et ressources.
Exporter un JSON, commencer une nouvelle campagne, puis importer le JSON ; l'import n'est
enregistré durablement qu'après **Sauver**. Tester un JSON invalide et le stockage bloqué :
une erreur doit être visible et la campagne courante rester exportable. Terminer le RTS avant
ces opérations. Les données locales dépendent de l'origine, du chemin du site et du navigateur.
Les sauvegardes locales du PC ne sont pas envoyées au site ; leur transfert se fait par JSON.

## État réel et références

Neuf PNG et six WAV originaux inclus dans le staging. Les sept effets sont générés par le code
inclus : il n'existe pas sept fichiers d'effets externes à inventer. Les six `.ogg` envisagés
historiquement sont absents ; les WAV existants sont utilisés.

237 tests Python sans Pygame réussis et syntaxe JS vérifiée. Le build Pygbag et le premier menu
ont été vérifiés dans Chromium sur GitHub Actions, avec capture inspectée. Le workflow bloque
désormais le déploiement si son test du menu échoue. Aucun navigateur n'est lancé sur le PC.
Les codecs audio à l'écoute, le jeu complet, les performances et les sessions dans Chrome/Edge
sur le PC restent à valider manuellement. Voir le [rapport du correctif](../docs/WEB_STARTUP_FIX_0_4_1.md).
Multijoueur Web : **ABSENT**, bouton explicite ; PC/LAN conservé.

Sources officielles pour les commandes et le comportement :

- [Pygbag 0.9.2 : boucle asynchrone et options](https://pypi.org/project/pygbag/0.9.2/).
- [Exemples Pygbag : navigateur et stockage](https://pygame-web.github.io/wiki/pygbag-code/).
- [GitHub Pages : workflows personnalisés](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
- [MDN : disponibilité et quotas du stockage Web](https://developer.mozilla.org/en-US/docs/Web/API/Web_Storage_API/Using_the_Web_Storage_API).

Rapport détaillé : [WEB_EDITION_0_4_1.md](../docs/WEB_EDITION_0_4_1.md).
