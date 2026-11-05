# STAR ARENA — V0.4.0 : multijoueur PC/LAN

## Livraison et portée

La campagne peut être hébergée par un joueur, avec deux ou trois participants humains et des factions distinctes. Une seule simulation s'exécute chez l'hôte. Les clients, y compris l'interface locale de l'hôte, affichent les instantanés reçus et envoient des intentions. Aucun serveur central n'est nécessaire.

Le solo, les sprites, les effets et musiques, les sauvegardes de campagne et les règles existantes sont conservés. Aucune dépendance n'a été installée. Aucun jeu, navigateur, test graphique ou test audio réel n'a été lancé.

**Les batailles multijoueurs utilisent uniquement la résolution automatique existante, exécutée par l'autorité. Le RTS interactif reste disponible en solo.** Les participants reçoivent le même résultat : pertes, survivants et conquête. Le RTS interactif en réseau, WebRTC et les clients navigateur ne sont pas implémentés.

## Connexion manuelle

1. Sur chaque PC, lancer la même version depuis le dossier du projet : `.\.venv\Scripts\python.exe main.py`.
2. Hôte : ouvrir **Multijoueur PC / LAN**, puis **Créer une partie**. Choisir le nom, la graine et le port, par défaut 8765. L'adresse d'écoute `0.0.0.0` accepte les connexions LAN ; une adresse locale précise peut être choisie.
3. Relever l'IPv4 de l'hôte avec `ipconfig`. Communiquer cette adresse, le port et l'invitation affichée dans le salon aux autres joueurs.
4. Invité : ouvrir **Rejoindre / reconnecter**, renseigner son nom, l'adresse de l'hôte, le port et l'invitation. `127.0.0.1` fonctionne seulement sur le même ordinateur.
5. Choisir des factions distinctes. L'hôte choisit la taille de galaxie, puis démarre lorsque deux ou trois joueurs sont connectés.
6. Jouer la campagne. Les dépenses, constructions, transferts et déplacements sont validés par l'hôte. Lors d'une bataille, utiliser la résolution automatique ; le bouton RTS interactif indique cette limite.

Le jeu ne configure ni pare-feu ni routeur. Une autorisation Windows sur réseau privé peut nécessiter une intervention manuelle. Cette livraison vise le LAN : aucune traversée NAT, découverte Internet ou ouverture de port automatique n'est fournie. Le WebSocket LAN n'est pas chiffré. Une connexion distante via réseau privé chiffré et authentifié demanderait une configuration et une validation manuelles ; elle n'a pas été testée.

## Autorité et synchronisation

- `network/authority.py` possède la campagne et valide les commandes : identité, faction, propriété, ressources, séquence et état de session.
- `network/runtime.py` exécute le serveur et les clients asyncio dans le même processus. La cadence d'avancement cible est de 10 Hz ; les instantanés complets sont diffusés environ toutes les 0,3 seconde et après les commandes acceptées.
- `network/replica.py` expose une vue cliente : avancer la simulation ou appliquer directement un déplacement y lève une erreur. L'application n'avance jamais une campagne réseau localement, même après une déconnexion.
- `network/controller.py` relie l'interface aux intentions réseau ; `presentation/multiplayer_view.py` fournit les formulaires et le salon.
- Les factions humaines sont exclues des décisions économiques et militaires de l'IA. Les autres factions conservent leur comportement.
- F10 et les commandes administrateur sont désactivés pour tous en multijoueur, hôte compris.

Le transport WebSocket RFC6455 est implémenté avec la bibliothèque standard Python. Il gère le masquage, les fragments, ping/pong, la fermeture et les limites de taille. Son interface est séparée du protocole de jeu pour permettre de futurs adaptateurs. Cela ne constitue pas un client WebRTC ou une garantie de durcissement pour un serveur Internet public.

Les messages JSON entrants sont bornés : commandes de 16 Kio, états de 2,1 Mo, 30 commandes/s et 120 trames/s, 12 connexions simultanées au maximum. Chaque client possède une file de 16 réponses fiables et un seul instantané en attente, remplacé par le plus récent. Authentification : délai de 5 s ; écriture : 3 s ; silence réseau : 15 s ; ping périodique de 5 s. Les doublons de clés JSON, constantes non finies, champs inattendus et séquences rejouées sont refusés. Pas de pickle ou d'évaluation de code distant.

## Déconnexion, reconnexion et sauvegarde

Une place déconnectée reste réservée ; la campagne est suspendue tant qu'un humain manque. Il n'y a ni remplacement automatique par l'IA ni migration de l'hôte. Une bataille en attente attend sa résolution autorisée, puis tous reçoivent le résultat commun.

L'invitation commune permet de rejoindre un nouveau salon. Chaque place reçoit ensuite une clé personnelle de reconnexion : connaître seulement le nom ou l'invitation ne permet pas de reprendre cette place. Une place déjà connectée refuse une seconde connexion.

Les clés personnelles sont mémorisées par adresse dans `settings/network_reconnect.json`, séparément des sauvegardes, exclues de Git et du staging Web. Garder ce fichier privé. Il est également possible de renseigner la clé dans le formulaire. Si elle est perdue, l'hôte peut réinviter la place hors ligne depuis le salon rechargé : une nouvelle clé privée invalide l'ancienne.

Seul l'hôte sauvegarde, dans `saves/multiplayer.json`. L'enveloppe réseau version 1, protocole 1, contient le format de campagne 5 et l'allocation des participants ; seules les empreintes des clés de reconnexion y sont stockées. Les instantanés publics ne contiennent ni clés ni empreintes. La sauvegarde solo `saves/campaign.json` reste séparée. Une sauvegarde multijoueur existante incompatible n'est pas écrasée silencieusement.

Pour reprendre : choisir **Héberger la sauvegarde multijoueur**, reconnecter les invités puis démarrer/reprendre. Les identifiants, allocations, graine, taille et géométrie sont conservés ; modifier la taille d'une campagne chargée est refusé. L'invitation commune est renouvelée, les clés personnelles des invités restent utilisables. Le menu de session propose **Sauvegarder puis fermer** ; fermer directement la fenêtre ne sauvegarde pas automatiquement.

## Vérifications exécutées

Le rapport machine est `docs/LOGIC_TESTS_0_4_0.json` : **198 tests réussis, aucune erreur, aucun échec, aucun test ignoré**, dont 174 régressions conservées et 24 nouveaux tests réseau. Exécution du 5 novembre 2026, Python 3.12.14, environ 10,3 secondes, dans un seul processus sans Pygame ni fenêtre.

| Contrôle | Statut | Preuve / méthode |
| --- | --- | --- |
| Création, connexion et factions | OK | Vrais clients WebSocket et serveur sur 127.0.0.1, port éphémère ; troisième joueur accepté, quatrième refusé, faction dupliquée refusée. |
| Autorité et démarrage | OK | Invité empêché de démarrer ; propriété, champs injectés et commandes admin rejetés. |
| Déplacements et synchronisation | OK | Ordre envoyé par client, état de campagne reçu avec déplacement et identifiants. |
| Économie et production | OK | Dépense et production synchronisées ; séquence rejouée empêchée de dépenser deux fois. |
| Défenses orbitales | OK | Construction distante d'une station, progression et synchronisation de l'état. |
| Bataille commune | OK | Résolution automatique exécutée une seule fois et résultat commun ; rencontre invité contre IA détectée même sans l'hôte engagé. |
| Factions humaines | OK | Tests empêchant leur pilotage par l'IA ; régressions solo conservées. |
| Déconnexion et reconnexion | OK | Pause, place réservée, retour avec même identifiant, rejet d'une clé erronée ou d'une place déjà connectée. |
| Sauvegarde et reprise réseau | OK | Sauvegarde hôte, rechargement sur un nouveau serveur et reconnexion de l'invité avec sa clé. |
| Réinvitation | OK | Rotation de clé d'une place hors ligne ; ancienne clé invalidée. |
| Transport et limites | OK | Handshake RFC connu, trame masquée connue, trame non masquée refusée, authentification surdimensionnée refusée, spam déconnecté, délais et fermeture testés. |
| File et copie cliente | OK | Instantanés regroupés vers le plus récent, file fiable bornée, avancement et mutation directe de la copie refusés. |
| Interface et partie sur deux PC | NON TESTÉ | Aucune fenêtre lancée ; essais réels limités à la boucle locale. |
| RTS interactif multijoueur | ABSENT | Résolution automatique livrée ; RTS interactif solo conservé. |
| Client navigateur / WebRTC / Internet | ABSENT | Interfaces préparatoires uniquement ; aucun test de traversée de routeur. |

Le contrôle statique `docs/PYTHON_STATIC_CHECKS.json` a vérifié **60 fichiers Python, 200 imports locaux et 396 symboles**, sans erreur et sans importer Pygame ni le jeu. Les neuf PNG intégrés correspondent toujours aux empreintes du manifeste ; les tests des six WAV restent réussis.

Une erreur de fermeture a été reproduite puis corrigée : attendre `Server.wait_closed()` avant de fermer les connexions actives bloquait l'arrêt. L'écoute est maintenant fermée d'abord, les connexions et tâches sont nettoyées, puis la fermeture du serveur est attendue. Les tests concernés et toute la suite ont ensuite réussi. Les serveurs de test sont fermés ; aucun port LAN n'a été ouvert automatiquement.

Commandes de vérification utilisées : `tools/run_logic_tests.py --report` et `tools/check_static.py --report`, avec le Python isolé disponible dans l'environnement. Aucun logiciel n'a été installé.

## Fichiers concernés

Créés : les sept modules de `src/star_arena/network/` (`__init__`, `transport`, `protocol`, `authority`, `runtime`, `replica`, `controller`), `src/star_arena/presentation/multiplayer_view.py`, `tests/test_multiplayer.py`, ce rapport et `docs/LOGIC_TESTS_0_4_0.json`.

Modifiés : `src/star_arena/app.py`, `presentation/renderer.py`, `persistence.py`, `systems/simulation.py`, `systems/economy.py`, `systems/planets.py`, les versions dans `src/star_arena/__init__.py` et `pyproject.toml`, `.gitignore`, `README.md`, `AGENTS.md` et le rapport statique. La sérialisation de campagne a été extraite en fonction réutilisable sans changer le format solo. Aucun ancien dossier Godot, archive, sprite ou fichier audio n'a été supprimé.

## Validation manuelle restante

Sur deux PC du même LAN : vérifier les formulaires et le copier/coller, rejoindre avec l'IP de l'hôte, jouer une campagne à deux puis trois joueurs, observer déplacements et dépenses des deux côtés, résoudre une bataille, déconnecter/reconnecter un invité, sauvegarder puis reprendre. Vérifier également les volumes et le rendu en lançant le jeu soi-même. Les performances sur longues campagnes et réseaux plus lents restent à mesurer ; cette version diffuse des états complets, sans interpolation ni deltas avancés.

Les tests exécutés valident la logique et les échanges locaux. Ils ne suffisent pas à déclarer le parcours graphique ou le multijoueur entre deux ordinateurs stable.
