# Musiques originales STAR ARENA — V0.3.2

Six fichiers WAV réels sont livrés, composés par le générateur local `tools/generate_music.py`.
Ils utilisent uniquement des oscillateurs, des notes et des percussions synthétiques originales ;
aucune mélodie ni aucun échantillon n'a été téléchargé ou copié depuis Star Wars.
Ce sont des ambiances simples, pas un orchestre enregistré.

| Fichier réel | Vue | Durée | Lecture |
|---|---|---:|---|
| main_menu.wav | Menu | 8 s | Boucle |
| galaxy.wav | Carte | 8 s | Boucle |
| planetary.wav | Planètes | 8 s | Boucle |
| battle.wav | RTS | 8 s | Boucle |
| victory.wav | Victoire | 3,2 s | Une fois |
| defeat.wav | Défaite | 3,2 s | Une fois |

Format PCM 16 bits mono, 11 025 Hz, total 846 984 octets. Les entrées/sorties des fichiers sont
adoucies ; les transitions entre vues sont gérées par le gestionnaire musical.

Le moteur préfère un OGG valide du même nom si vous en fournissez un, sinon il charge le WAV.
Aucun des six fichiers .ogg n'est actuellement livré. Les pistes manquantes ou invalides restent
silencieuses sans arrêter le jeu. Relancer le jeu après ajout ou remplacement d'une piste.

Le générateur conserve les fichiers WAV déjà présents ; il ne remplace pas vos compositions.
Les tests vérifient les en-têtes et les échantillons sur disque, et simulent le chargement Pygame.
Aucune écoute ni lecture réelle automatique n'a été effectuée.
