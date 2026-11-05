# Admin et effets sonores — 5 novembre 2026

> Historique V0.3.0 : les préférences persistantes, la musique et le nouveau comportement
> F8 sont désormais décrits dans `AUDIO_UPDATE_0_3_1.md`.

F10 ouvre/ferme le panneau admin ; Échap le ferme aussi. La simulation et les contrôles
sous-jacents sont suspendus pendant son ouverture. F8 active/coupe le son dans toutes les vues.

## Commandes

| Commande | Effet |
|---|---|
| Ressources | +10 000 crédits et minerais à la seule faction du joueur |
| Flotte | 5 chasseurs, 2 corvettes, 1 croiseur aux statistiques normales, nouveaux identifiants, dans un système allié sélectionné |
| Réparer | Coques/boucliers alliés vivants restaurés ; aucune résurrection |
| Accélérer les files | Commandes existantes déjà payées, durée réduite à 1 seconde chacune ; effets de pénurie conservés |
| Éliminer les ennemis | En RTS uniquement, destruction des unités ennemies et réserves, puis résolution normale et persistante |

Les commandes exigent l'ouverture explicite du panneau. Les cheats de campagne refusent les
engagements en cours afin de préserver leurs compositions. Ils ne changent pas les coûts ou
statistiques normaux. Les conséquences sont sauvegardables au format existant, avec F5 après
fermeture du panneau. Le panneau ouvert et la préférence sonore ne sont pas sauvegardés.

## Audio

Sept effets synthétiques originaux, sans échantillon téléchargé : clic, ordre, laser, impact,
bouclier, explosion et confirmation. PCM mono 22 050 Hz / 16 bits, volume de lecture 22%,
durée maximale 0,28 seconde, synthèse déterministe et cache par effet. Les tirs/impacts/boucliers
sont limités à une lecture par 100 ms et les explosions à une par 180 ms ; huit canaux maximum
lors de l'initialisation par le jeu. Pas de musique ni de doublage dans cette livraison.

Le backend audio est injecté dans la présentation. L'import du jeu ou des tests n'initialise
pas SDL/mixer. Le mixer démarre lors du lancement manuel ; un échec d'initialisation ou de
lecture désactive les sons, sans arrêter la partie. La perte de focus/minimisation coupe les
sons en cours. Le moteur de simulation ne dépend pas de l'audio. Les sons de combat observent
les projectiles et effets visuels ; les confirmations observent le dernier événement du journal.
Des événements très rapprochés peuvent être regroupés ou masqués par une notification plus récente.

## Validation exécutée

- 118 tests de logique réussis, 0 échec/erreur/ignoré, Python 3.12.14, environ 0,67 seconde.
- 12 nouveaux tests : stocks et sauvegarde, identifiants et statistiques de flotte, réparation,
  refus pendant engagement, panneau obligatoire et pause, files séquentielles, victoire et
  résolution unique, routage F10/F8/Échap et focus, génération PCM, cache/volume/limitation,
  mute et périphérique audio indisponible.
- Backend audio entièrement simulé ; aucun import de Pygame, aucun périphérique ouvert,
  aucune fenêtre ni lecture sonore. Les données PCM seules ont été générées pendant le test.
- Analyse statique : 39 fichiers Python, 119 imports locaux, 267 symboles, aucune erreur.
- Preuves : `LOGIC_TESTS_0_3_0.json` et `PYTHON_STATIC_CHECKS.json`.

La qualité sonore, le mixage réel, la disponibilité du périphérique et le rendu du panneau
restent à vérifier manuellement en lançant le jeu. Aucun test graphique ou sonore automatique
n'a été lancé et aucune dépendance n'a été installée.

## Fichiers

Créés : `src/star_arena/systems/admin.py`, `src/star_arena/presentation/audio.py`,
`tests/test_admin_audio.py`, `docs/ADMIN_ET_SONS.md`.
Modifiés : `src/star_arena/app.py`, `src/star_arena/presentation/renderer.py`, `README.md`
et les deux rapports JSON de vérification. Les assets PNG, statistiques de combat et formats
de sauvegarde sont conservés.
