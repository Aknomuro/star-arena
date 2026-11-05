# STAR ARENA — V0.3.2 : Fleet Navigation & Audio Fix

Date : 5 novembre 2026. Version Python 0.3.2 ; sauvegardes JSON **5**.

## Causes identifiées

### Déplacements

Le code ne calculait pas de chemin : `movement_error` imposait une route directe vers un
voisin et refusait tout ordre si `travel` existait déjà. L'objet de voyage ne décrivait qu'un
segment. À l'arrivée, aucune destination finale n'était conservée pour continuer.
Le symptôme de déplacement manuel de proche en proche est expliqué directement par ces règles.

### Audio

Constats démontrés par inspection et tests simulés :

- La V0.3.1 ne livrait aucune des six musiques : les emplacements étaient documentés, avec un
  repli silencieux. C'était la cause certaine de l'absence de musique fournie par le projet.
- Les effets refusaient tout format négocié différent de `(22050, -16, 1)`. Une sortie stéréo
  ou une autre fréquence pouvait donc désactiver les effets même avec un mixer initialisé.
- Les tirs et impacts étaient déduits des objets visuels encore présents à l'image suivante.
  Un projectile ou effet créé puis retiré entre deux images pouvait ne produire aucun son.
- La sélection directe d'un système/planète n'appelait pas le son de clic.
- Seule la dernière entrée du journal pouvait déclencher une fin de construction ; une autre
  notification plus récente pouvait masquer cet événement.
- Les effets étaient modérés et la musique pouvait les couvrir, sans baisse temporaire du mixage.

Le fichier de préférences présent au moment de l'inspection indiquait : volume principal 80%,
musique 95%, effets 70%, canaux activés et mute général désactivé. Il n'a pas été remplacé ou
réinitialisé. Aucune variable `SDL_AUDIODRIVER` ou `SDL_AUDIO_DEVICE_NAME` n'était définie dans
l'environnement inspecté. Ce ne sont donc pas les causes constatées à ce moment-là.

Le périphérique Windows réel et son routage n'ont pas été testés : aucun mixer réel, aucune
fenêtre et aucune lecture audio n'ont été lancés, conformément aux consignes. Le format exact
négocié sur ce PC reste à constater au lancement manuel. La synthèse PCM et la présence des
WAV ne sont pas présentées comme une preuve d'audibilité.

## Navigation livrée

Dijkstra minimise la somme des durées `max(2, distance / vitesse)` des routes existantes.
Il n'ajoute aucun saut arbitraire. Le clic droit sur une destination accessible calcule le
trajet complet. Une destination inconnue ou inaccessible donne un message sans modifier l'ordre.

Chaque flotte permanente conserve sa destination finale, son itinéraire, l'indice du segment
et son état. Le segment actif conserve origine, destination, durée et temps écoulé. Les étapes
s'enchaînent sans intervention ; pause et ×1/×2/×4 s'appliquent au même pas fixe que l'économie.
Le rendu surligne le chemin complet et affiche étapes, destination, progression, état et ETA.
L'ETA est exprimée en secondes simulées et exclut les délais des batailles et occupations.

Un nouvel ordre en vol conserve le segment actif, sa position et son temps écoulé. La nouvelle
route débute au prochain système ; même un retour vers l'origine passe d'abord par la fin du
segment engagé. La flotte et ses unités ne sont ni recréées ni téléportées.

Si une route future disparaît, le jeu recalcule le chemin à l'étape suivante en conservant
l'historique parcouru. Sans alternative, la flotte reste au système courant, état **Bloquée**,
et repart quand un chemin devient disponible. Un segment déjà engagé reste parcouru jusqu'à
son terme même si sa route est supprimée entre-temps. Le format 5 autorise de sauvegarder une
carte temporairement déconnectée et un segment précédemment engagé. Les nouvelles galaxies
sont toujours générées connexes.

### Traversées et combats

- Système allié : traversée sans nouvel ordre.
- Système neutre ou ennemi non défendu : traversée sans annexion automatique intermédiaire.
  Seul l'arrêt final revendique le système sans combat.
- Flotte hostile ou défense construite : arrêt et engagement, avec stations et milices existantes.
- Victoire : application normale de la conquête et des pertes, puis reprise au prochain pas de
  campagne, après retour à la galaxie. Une arrivée hostile déjà en attente est traitée avant départ.
- Défaite : destination et itinéraire annulés ; repli, capture ou destruction selon les règles
  existantes. Les garnisons ne reçoivent pas d'ordre de navigation.

Les sièges terrestres restent indépendants : poursuivre sa route après une victoire spatiale
peut laisser une occupation en attente faute de flotte permanente sur place.

### Sauvegardes

Le JSON 5 conserve trajet, segment, progression et ordre suspendu par un engagement.
Les formats 1 à 4 compatibles restent lisibles. Un ancien voyage sans itinéraire devient un
ordre à un segment, sans remise à zéro de sa progression. À l'enregistrement, l'ancien fichier
est archivé selon la règle existante (`.v4.bak` pour le format 4, numéroté si nécessaire).
Les sauvegardes de l'utilisateur n'ont pas été utilisées comme fixtures de test.

## Audio corrigé et musiques réelles

Les effets acceptent le PCM signé 16 bits mono ou stéréo, entre 8 et 96 kHz. La synthèse adapte
fréquence et nombre de canaux au format réel du mixer ; un changement de format invalide le cache.
Le mixer utilise huit canaux à son initialisation ; deux sont réservés aux clics, ordres et
confirmations. Les effets de combat utilisent les autres canaux disponibles, sans forcer le
remplacement d'un son prioritaire. Les limitations temporelles existantes sont conservées.

La synthèse utilise désormais une amplitude de base plus élevée. Pendant les effets, la musique
baisse progressivement jusqu'à 30% de son gain courant, puis retrouve son niveau sans modifier
les préférences. Cela aide notamment lorsque le volume musical a été réglé très haut.
L'équilibre réel reste à ajuster à l'écoute.

Les clics de sélection sont déclenchés explicitement. Les confirmations de construction sont
raccordées aux commandes acceptées. Les tirs, impacts, boucliers et explosions disposent de
compteurs d'événements bornés en taille, observés par la présentation : ils ne dépendent plus de
la durée de vie d'un objet visuel entre deux images. Plusieurs événements du même type sont
regroupés et limités pour éviter une avalanche de lectures. Les fins de construction examinent
les nouvelles entrées du journal conservé, pas seulement la dernière.

### Six compositions créées sur disque

Source reproductible : `tools/generate_music.py`. Génération hors ligne avec uniquement la
bibliothèque standard, sans import de Pygame ni lecture sonore. Les fichiers déjà présents
sont conservés par le générateur. Aucun téléchargement, échantillon externe ou mélodie de
Star Wars n'a été utilisé. Il s'agit d'ambiances synthétiques originales simples, avec basse,
arpèges et, pour la bataille, percussion synthétique ; pas d'un orchestre enregistré.

| Fichier réel sous assets/audio/music/ | Durée | Taille | Lecture |
|---|---:|---:|---|
| main_menu.wav | 8 s | 176 444 octets | Boucle |
| galaxy.wav | 8 s | 176 444 octets | Boucle |
| planetary.wav | 8 s | 176 444 octets | Boucle |
| battle.wav | 8 s | 176 444 octets | Boucle |
| victory.wav | 3,2 s | 70 604 octets | Une fois par résultat |
| defeat.wav | 3,2 s | 70 604 octets | Une fois par résultat |

Format réel : WAV PCM mono 16 bits, 11 025 Hz ; total **846 984 octets**. Les six contenus sont
distincts et non silencieux, avec leur totalité d'échantillons vérifiée. Inventaire et SHA-256 :
`docs/MUSIC_ASSETS_0_3_2.json`. Aucun des six OGG n'a été créé ; un OGG valide fourni sous le nom
correspondant reste prioritaire, avec repli sur le WAV réel. Le gestionnaire appelle bien
`pygame.mixer.music.load` et `play` au lancement manuel ; ces appels ont été exercés uniquement
sur un backend simulé pendant les tests. Les fondus existants sont conservés.

### Paramètres et diagnostic manuel

Les paramètres conservent les volumes principal/musique/effets et leurs activations séparées.
F8 reste le mute général ; un indicateur apparaît quand le son est coupé ou si le mixer a échoué.
Deux boutons ajoutés : **Tester effets** et **Tester musique**. Ils respectent le mute et les
volumes, signalent un canal coupé ou un échec et ne prétendent pas confirmer une écoute réussie.

Le panneau affiche le nombre de pistes valides et le format négocié. Les sorties audio sont
énumérées via SDL uniquement lors du lancement manuel réel, si cette API est disponible.
Cette énumération facultative ne décide pas à elle seule de la réussite de l'audio.
Les erreurs d'initialisation, de format ou de lecture restent affichables. Les préférences
existantes sont conservées dans leur fichier séparé ; aucune préférence audio n'est injectée
dans les données de campagne.

## Tests exécutés

**156 tests réussis, 0 échec, 0 erreur, 0 ignoré**, Python 3.12.14, environ 1,89 seconde lors du
dernier passage. Un seul processus de test léger, aucun import de Pygame ni périphérique audio.
136 tests précédents et 20 nouveaux tests V0.3.2. Preuve : `docs/LOGIC_TESTS_0_3_2.json`.

| Vérification | Statut | Méthode |
|---|---|---|
| Trajet direct et multi-étapes | OK | Itinéraire 0→1→2→3, ETA 6 s, arrivée et composition conservées |
| Pondération temporelle | OK | Dijkstra évite une route géométriquement très longue |
| Traversée sans conquête | OK | Systèmes neutres et ennemi non défendu restent inchangés pendant transit |
| Destination inaccessible | OK | Refus sans mutation de la route existante |
| Changement en vol | OK | Position et segment identiques immédiatement, puis retour par les routes |
| Pause et accélérations | OK | Horloge et indice de segment exacts sous pause, ×1, ×2, ×4 |
| Route supprimée | OK | Recalcul avec historique conservé ; blocage sans chemin ; reprise après réouverture |
| Segment engagé supprimé | OK | Sauvegarde/recharge sans réinitialisation et achèvement du segment |
| Engagement en chemin | OK | Ordre suspendu, sauvegarde pendant engagement, reprise après victoire |
| Défaite | OK | Ordre effacé et repli vers un refuge conforme aux anciennes règles |
| Sauvegarde en transit | OK | Égalité complète après recharge, puis simulation identique jusqu'à destination |
| Migration V4 | OK | Progression conservée et copie `.v4.bak` identique au fichier original |
| Six WAV réels | OK fichiers | En-têtes, format, durée, taille, échantillons non nuls et contenus distincts |
| Chargement WAV par le gestionnaire | OK simulé | Appels load/play observés sur le backend de musique factice |
| Format stéréo négocié | OK simulé | Sortie 48 kHz / 16 bits / stéréo acceptée, PCM et cache adaptés |
| Événements brefs | OK logique | Sons de tirs et explosions signalés même après disparition des objets visuels |
| Fins de construction | OK logique | Confirmation trouvée même si une autre entrée du journal est plus récente |
| Boutons audio, mute, périphérique | OK simulé | Respect du mute, demande de lecture et message d'erreur sans crash |
| Baisse musicale temporaire | OK simulé | Gain réduit à 30%, puis restauré, préférences inchangées |
| Régressions | OK | Anciens tests d'économie, flottes, combats, stations, milices, sièges, sauvegardes, audio et préférences |
| Analyse statique | OK | 45 fichiers Python, 141 imports locaux, 305 symboles ; aucune erreur |
| Neuf sprites PNG | OK fichiers | 9 empreintes identiques au manifeste, aucun remplacement |
| Audibilité sur le PC et sorties Windows | NON TESTÉ | Aucun périphérique réel ouvert, aucune lecture sonore |
| Rendu et clic droit en fenêtre | NON TESTÉ | Aucune fenêtre graphique lancée |

## Fichiers créés ou modifiés

Créés :

- `src/star_arena/systems/navigation.py` — Dijkstra, ordres, segments et ETA.
- `tools/generate_music.py` — générateur reproductible sans lecture.
- `tests/test_navigation_audio_fix.py` — 20 tests complémentaires.
- Les six fichiers WAV listés ci-dessus.
- `docs/ETAT_PROJET_PYTHON_0_3_2.md`, `docs/MUSIC_ASSETS_0_3_2.json`, `docs/LOGIC_TESTS_0_3_2.json`.

Modifiés :

- `src/star_arena/domain/models.py` — données d'itinéraire de flotte.
- `src/star_arena/systems/simulation.py` — progression et règles de traversée.
- `src/star_arena/systems/combat.py` — suspension et annulation des ordres.
- `src/star_arena/systems/tactical.py` — compteurs d'événements pour la présentation.
- `src/star_arena/persistence.py`, `config.py` — format 5 et migration.
- `src/star_arena/presentation/audio.py` — format négocié, cache et canaux.
- `src/star_arena/presentation/music.py` — WAV de repli et baisse musicale temporaire.
- `src/star_arena/app.py` — sélections, confirmations et tests audio explicites.
- `src/star_arena/presentation/renderer.py` — trajet, ETA, états et paramètres audio.
- `src/star_arena/__init__.py`, `pyproject.toml` — version 0.3.2.
- `README.md`, `AGENTS.md`, `assets/audio/music/README.md` — documentation actualisée.
- `docs/PYTHON_STATIC_CHECKS.json` — analyse exécutée.

Aucun logiciel installé, aucun fichier du jeu supprimé, aucune archive ou ancien projet Godot
modifié. Les sprites et les règles de statistiques des unités sont conservés.

## Vérifications manuelles restantes

1. Relancer le jeu, sélectionner une flotte, cliquer droit sur un système éloigné et observer
   les étapes, l'ETA, la pause et les accélérations. Redonner une destination pendant le vol.
2. Sauvegarder à mi-parcours, recharger puis vérifier la continuation et un engagement sur le trajet.
3. Dans Paramètres audio, vérifier F8, les activations et volumes ; cliquer « Tester effets »
   et « Tester musique ». Vérifier le format et la sortie audio affichés, ainsi que le mixeur Windows.
4. Écouter menu/galaxie/planètes/RTS/résultats et vérifier que les effets restent audibles dans une bataille.

La correction logicielle est testée. L'absence d'écoute réelle empêche de confirmer la résolution
matérielle du silence sur ce PC ou de déclarer le mixage terminé. Les musiques sont des boucles
synthétiques simples et courtes ; un habillage orchestral plus développé reste un travail distinct.
