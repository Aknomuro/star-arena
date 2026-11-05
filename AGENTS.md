# STAR ARENA — version Python

Le projet actif est maintenant le paquet Python `src/star_arena`, lancé par `main.py`.
État courant : V0.4.1, adaptation Web non validée dans un navigateur,
documentée dans `docs/WEB_EDITION_0_4_1.md` ; PC/LAN dans `docs/MULTIPLAYER_0_4_0.md`.
Le socle planétaire est décrit dans `docs/ETAT_PROJET_PYTHON_0_3_DEFENSES.md`.
Ne pas utiliser Godot ni un serveur MCP pour son développement. Préserver les anciens
dossiers Godot et les archives.

Le PC a subi des plantages Windows 0x10E. Ne lancer ni jeu, ni test graphique,
ni navigateur, ni traitement lourd automatiquement. Les vérifications statiques
et les tests de logique sans Pygame ni fenêtre sont autorisés par la demande V0.2.
Les exécuter dans un seul processus léger. L'utilisateur lance le jeu graphique.
Ne pas installer automatiquement de logiciel ou de dépendances.

La simulation et les données ne doivent pas importer Pygame. Le rendu et les entrées
restent dans `presentation` et `app.py`. La V0.3 implémente les batailles RTS, la conquête, l'économie de faction et les
chantiers navals, les planètes, les défenses orbitales et les milices ; préserver les neuf sprites PNG intégrés.

Ne lancer aucun test audio réel. Musique et effets restent dans presentation ;
les tests utilisent uniquement des backends simulés et n’importent pas Pygame.

La préparation Web reste sans installation/export automatique. F7 réduit uniquement la
présentation ; préserver les statistiques et les anciens formats de campagne.

Réseau : seule Authority avance la simulation ; CampaignReplica est une vue cliente.
Les tests réseau locaux 127.0.0.1 sont autorisés, dans le même processus de tests,
sans ouvrir de port LAN automatiquement ni modifier pare-feu/routeur.
Le RTS interactif multijoueur et WebRTC ne sont pas livrés ; combats MP automatiques.

Web : BrowserStore utilise le pont JS et localStorage ; aucune écriture de campagne Web
via la persistance fichier PC. Ne pas importer le serveur LAN dans la branche navigateur.
Le staging `web_build/arena` est une copie source/assets, pas un build WASM testé.
Pygbag et le workflow Pages restent manuels ; ne pas les lancer, installer ou publier
automatiquement. Préserver les sauvegardes lors d'erreurs de stockage et de validation.
