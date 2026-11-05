# Sprites de flotte — préparation V0.2.1

**Neuf PNG réels du pack V9 sont intégrés depuis le 5 novembre 2026.**
Les copies sont identiques aux originaux ; aucun PNG fictif ni recoloration n'a été créé.
Correspondances et contrôles : `docs/ASSETS_PNG_INTEGRES.md` à la racine du projet.

| Dossier | Palette du secours vectoriel | Fichiers utilisés |
|---|---|---|
| `republic/` | Coque blanche, détails bleus | `fighter.png`, `corvette.png`, `cruiser.png` |
| `empire/` | Coque gris foncé, détails rouges | `fighter.png`, `corvette.png`, `cruiser.png` |
| `alliance/` | Coque blanc cassé, détails orange | `fighter.png`, `corvette.png`, `cruiser.png` |

Le fichier `manifest.json` conserve les noms d'origine, les empreintes SHA-256 et
le cap natif. Les neuf PNG V9 pointent vers le haut : un décalage de −90° est appliqué
uniquement à l'affichage. Un futur PNG orienté à droite doit déclarer `forward: right`.

Les fichiers sont facultatifs et indépendants. Le chargeur essaie d'abord le fichier
de faction, puis l'ancien fichier générique `assets/ships/<classe>.png`, puis le
dessin vectoriel si le fichier manque ou ne peut pas être décodé.

Pour les futures images : vue 2D de dessus, coque orientée vers la droite par défaut,
silhouette nette et reconnaissable, style non pixel art et sans aspect cartoon mobile.
Préférer des PNG RGBA sur fond transparent, avec peu de marge vide. Le chargeur
préserve les proportions et l'alpha ; il ne détoure ni ne recolore les PNG automatiquement.

Les trois classes ont des tailles visuelles distinctes, indépendantes des hitboxes :
longueur de référence 42 / 72 / 112 unités pour chasseur / corvette / croiseur.
La dimension la plus longue de l'image est ajustée à cette taille avec conservation
du ratio, à l'arrondi au pixel près. La rotation lissée utilise des pas d'un demi-degré.

Les originaux ne sont décodés qu'une fois par chemin pendant une session, même en
cas d'échec. Ils sont ramenés à 512 pixels au plus sur le grand côté en mémoire.
Les tailles et rotations ont des caches LRU bornés. Aucun fichier source n'est modifié.
Un PNG doit faire au plus 8 Mo, 4 096 pixels par dimension et quatre millions de pixels.
La lecture de son en-tête précède le décodage pour contrôler ces bornes.

Ajouter les PNG avant le lancement, ou redémarrer le jeu après leur ajout. Aucun
chargement Pygame n'est exécuté par les contrôles automatisés sans fenêtre.

Inventaire sans fenêtre : `python tools/audit_ship_assets.py --report`.
Résultat : `docs/SHIP_ASSETS_0_2_1.json`.
