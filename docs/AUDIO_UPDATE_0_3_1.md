# STAR ARENA — Audio Update V0.3.1

Date : 5 novembre 2026. Version applicative 0.3.1 ; format des campagnes inchangé (JSON 4).

## Résultat livré

Gestionnaire musical séparé des effets, utilisant exclusivement le canal `pygame.mixer.music`.
Aucun fichier musical réel n'était présent dans `assets/` lors de l'inspection. Le repli choisi
est le silence pour les pistes absentes ; aucune musique orchestrale n'a été composée,
téléchargée ou présentée comme disponible. Aucun OGG vide ou factice n'a été placé dans les assets.
Les sept effets synthétiques originaux sont conservés.

### Ambiances et inventaire réel

Le dossier `assets/audio/music/` est créé avec un README de composition et d'intégration.
L'inventaire a vérifié chaque chemin et les en-têtes éventuels sans décodage ni lecture sonore.
Preuve : `docs/MUSIC_ASSETS_0_3_1.json`.

| Fichier attendu | Ambiance originale souhaitée | Présence réelle | Lecture prévue |
|---|---|---|---|
| main_menu.ogg | Thème spatial majestueux, cuivres, cordes et synthétiseurs | ABSENT | Boucle |
| galaxy.ogg | Stratégie et exploration, pulsation discrète | ABSENT | Boucle |
| planetary.ogg | Calme et mystère, nappes et cordes douces | ABSENT | Boucle |
| battle.ogg | Orchestral militaire intense, percussions et cuivres | ABSENT | Boucle |
| victory.ogg | Court thème triomphal | ABSENT | Une fois par résultat |
| defeat.ogg | Court thème dramatique | ABSENT | Une fois par résultat |

**0 piste disponible sur 6.** Les six catégories nécessitent encore un fichier audio original
ou utilisable sous licence. Il n'y a pas de copie de mélodie protégée ni de téléchargement.
Ajouter des OGG Vorbis compatibles avec SDL_mixer puis relancer le jeu. La vérification légère
OggS ne garantit pas qu'un fichier soit décodable ; les erreurs de codec sont gérées à la lecture.

### Gestion musicale

- Choix automatique au menu, dans la galaxie, la vue planétaire et la bataille RTS.
- Victoire/défaite dès le résultat RTS, puis continuité sur le rapport du même engagement.
  Une égalité utilise l'ambiance galactique, sans faux thème de victoire.
- Les quatre ambiances bouclent ; les deux thèmes courts sont lus une fois par résultat.
- Une sélection de système, planète, flotte ou page ne recharge pas la piste.
- Sortie progressive sur 0,75 seconde, puis chargement de la nouvelle piste à volume nul et
  entrée progressive sur 0,75 seconde. C'est un fondu séquentiel, sans superposition de deux
  pistes : `mixer.music` ne streame qu'une musique à la fois.
- Aucune attente bloquante, aucun thread ni processus supplémentaire. Les fondus suivent le
  temps réel, indépendamment des vitesses de simulation et de la pause de campagne.
- Perte de focus : pause musicale ; retour : reprise sans rechargement.
- Mute/volume conservent la piste courante au lieu de la relancer. Une scène différente pendant
  le mute conserve le suivi des ambiances, avec lecture silencieuse si le mixer est disponible.
- Fichier absent, vide, trop volumineux (>100 Mo), sans signature OggS ou non décodable : silence
  sans bloquer la partie. Une erreur de décodage n'est pas réessayée à chaque image.
- Si le périphérique est indisponible, le jeu reste utilisable sans audio. Les initialisations
  sont réservées au lancement manuel et aux actions audio explicites, jamais à l'import.

### Paramètres et volumes

Accès : bouton **Paramètres audio** du menu principal ou du panneau admin F10. Le panneau
suspend la simulation sous-jacente, pas la musique. Échap ou « Retour au jeu » le ferme.

- Volume principal : 80% par défaut.
- Volume musique : 35% par défaut, gain final `principal × musique`.
- Volume effets : 70% par défaut, gain final `0,4 × principal × effets` ; ce coefficient garde
  un niveau proche des effets précédents (22,4% avec les réglages par défaut).
- Réglages par pas de 10 points, bornés entre 0 et 100%.
- Activation séparée de musique et effets.
- F8 applique un mute général et le retire en conservant les activations et volumes individuels.
- La musique fonctionne aussi lorsque les effets sont désactivés, grâce au mixer partagé.
- Le volume des effets déjà en cache est mis à jour immédiatement ; les sept sons ne sont pas
  régénérés à chaque changement de volume.

Préférences : `settings/audio.json` depuis les sources, hors `saves/campaign.json`. Après
installation du paquet, le fichier est sous `StarArena/settings` à côté du dossier de sauvegarde
utilisateur. Le chemin est dérivé de la racine de données, sans écrire dans le paquet installé.
Enregistrement atomique à chaque modification ; aucun besoin de sauvegarder la campagne.
Le premier lancement sans fichier utilise les valeurs par défaut. Les volumes non finis,
hors limites, les types invalides et les versions inconnues sont refusés. Un fichier invalide
est préservé ; les contrôles fonctionnent pour la session avec un message indiquant que
l'enregistrement n'a pas abouti. Les réglages ne sont jamais ajoutés à la sauvegarde de campagne.

### Effets et gameplay préservés

Clic, ordre, laser, impact, bouclier, explosion et confirmation restent disponibles, synthétisés
en mémoire et mis en cache. Les limitations de répétition et le plafond de huit canaux sont
conservés. La simulation, les statistiques, les sprites et les fichiers de campagne ne dépendent
pas du gestionnaire musical. Aucun changement de règle de combat ou de format de sauvegarde.
Le mixage réel devra être ajusté à l'écoute avec les futures pistes, dont la sonie est inconnue.

## Vérifications exécutées

Un seul processus Python léger à la fois, sans import de Pygame, fenêtre, décodage réel,
périphérique audio ou lecture sonore. Aucune dépendance installée.

**136 tests réussis, 0 échec, 0 erreur, 0 ignoré**, Python 3.12.14, environ 1,22 seconde.
Cela inclut les 118 régressions et 18 nouveaux tests musique/préférences.
Preuve : `docs/LOGIC_TESTS_0_3_1.json`.

| Vérification | Statut | Méthode |
|---|---|---|
| Changements d'ambiance et boucles | OK logique | Backend music simulé : chargement menu/galaxie, `loops=-1`, variation progressive du gain |
| Sélection sans redémarrage | OK logique | 100 demandes identiques, un seul chargement et une seule lecture |
| Victoire/défaite | OK logique | `loops=0`, non-répétition du même résultat, nouveau thème pour un nouvel engagement |
| Continuité RTS/rapport | OK logique | Même catégorie et identifiant de résultat dans les deux vues |
| Volume et mute musique | OK logique | Gains, mise à zéro et rétablissement sans rechargement |
| F8 général et activations séparées | OK logique | Mute commun, restauration des préférences et musique indépendante des effets |
| Mixer sans effets | OK logique | Initialisation partagée avec effets désactivés, musique activée |
| Focus | OK logique | Pause/reprise uniques, sans nouveau chargement |
| Absence/format invalide | OK logique | Dossier temporaire vide, fichier vide et signature invalide : aucune lecture demandée |
| Codec défaillant | OK logique | Backend rejetant le chargement : erreur mémorisée, pas de boucle de tentatives |
| Périphérique indisponible | OK logique | Initialisation ou accès simulé en échec : aucun crash et aucune lecture |
| Préférences persistantes | OK logique | Aller-retour JSON dans un dossier temporaire distinct de la campagne |
| Préférences invalides | OK logique | Valeurs interdites refusées et fichier inconnu conservé à l'identique |
| Réglages malgré erreur de fichier | OK logique | Valeur modifiée pour la session et erreur d'enregistrement affichable |
| Pause de la vue paramètres | OK logique | Campagne inchangée panneau ouvert, reprise après fermeture |
| Analyse statique | OK | 42 fichiers Python, 126 imports locaux, 281 symboles ; aucune erreur |
| Inventaire de vraies musiques | ABSENT | Six fichiers recherchés explicitement, aucun présent |
| Lecture réelle et mixage | NON TESTÉ | Aucun test sonore réel autorisé ; fichiers musicaux absents |
| Interface graphique | NON TESTÉ | Aucun lancement Pygame automatique |

Les fichiers OGG utilisés dans les tests sont de minuscules fixtures d'en-tête dans les
répertoires temporaires des tests, supprimées par leur contexte. Le backend simulé ne les
décode jamais ; ce ne sont pas des compositions musicales et ils ne sont pas livrés dans les assets.

## Fichiers créés ou modifiés

Créés :

- `src/star_arena/presentation/music.py` : inventaire et gestionnaire musical.
- `src/star_arena/presentation/audio_settings.py` : préférences validées et écriture indépendante.
- `tests/test_music.py` : 18 tests sans périphérique.
- `assets/audio/music/README.md` : emplacements et intentions de composition originales.
- `docs/AUDIO_UPDATE_0_3_1.md`, `docs/MUSIC_ASSETS_0_3_1.json` : présent rapport et inventaire.
- `docs/LOGIC_TESTS_0_3_1.json` : résultats de logique de cette version.

Modifiés :

- `src/star_arena/presentation/audio.py` : volume des effets et mise à jour du cache.
- `src/star_arena/app.py` : F8 général, paramètres, préférences et suivi musical des vues.
- `src/star_arena/presentation/renderer.py` : panneau audio et ses accès.
- `src/star_arena/__init__.py`, `pyproject.toml` : version 0.3.1.
- `tests/test_admin_audio.py` : contexte explicite du premier F8 dans le test de routage.
- `README.md`, `AGENTS.md`, `docs/ADMIN_ET_SONS.md` : documentation actuelle et lien historique.
- `docs/PYTHON_STATIC_CHECKS.json` : analyse exécutée.

## Intervention manuelle restante

Créer ou fournir les six compositions originales ou sous licence ; les copier aux emplacements
indiqués puis relancer le jeu. Tester à l'écoute les transitions, boucles, résultats, paramètres,
F8 et retour de focus. Vérifier que les tirs restent lisibles dans le mixage musical.
Le système logiciel est livré ; les six compositions orchestrales et leur validation auditive
ne sont pas terminées et ne sont pas déclarées disponibles.
