# V0.4.1 — correctif SDL_gfx / Pygbag

## Problème confirmé par le traceback utilisateur

Opera GX atteint la galaxie puis `pygame.gfxdraw.aacircle` lève
`pygame.error: Parameter 'renderer' is invalid`. L'extension est importable mais son
interface SDL_gfx n'est pas utilisable sur ce runtime. L'ancien contrôle de présence
du module ne suffisait donc pas. Les appels directs à gfxdraw étaient limités aux
contours de cercles dans `presentation/art.py`.

## Rendu conservé et replis

| Élément | Comportement |
| --- | --- |
| Cercles PC | `pygame.draw.circle` puis anticrénelage gfxdraw tant que celui-ci fonctionne. |
| Cercles Web | Aucun import ni appel à gfxdraw ; petites surfaces transparentes suréchantillonnées ×2 puis `smoothscale`, mises en cache. |
| Erreur SDL connue sur PC | Cercle de base déjà tracé, avertissement explicite, fonction gfxdraw désactivée pour ce Painter ; supersampling aux appels suivants. |
| Petits cercles hors budget / grands rayons | `pygame.draw.circle` direct ; pas de surface temporaire géante. |
| Lignes | `pygame.draw.line`, et `pygame.draw.aaline` quand demandé et disponible. La même erreur SDL connue désactive seulement aaline, avec avertissement et repli line. |
| Polygones et ellipses | Primitives `pygame.draw` directes, sans gfxdraw. Les appels de la galaxie et des batailles sont centralisés dans Painter. |
| Transparence, panneaux, halos, planètes | Surfaces SRCALPHA et primitives draw ; masque et supersampling existants des planètes conservés. |
| Autres erreurs | Propagées : aucun `except: pass`, aucune interception générale silencieuse. |

Seul le message exact `Parameter 'renderer' is invalid` (casse/espaces normalisés) est
reconnu comme incompatibilité optionnelle. Les autres `pygame.error`, `TypeError` et
`RuntimeError` ne sont pas masqués. Les défaillances sont conservées dans
`Painter.compatibility_errors` et signalées par `RuntimeWarning`, une seule fois par
fonction défaillante puisque cette fonction n'est ensuite plus appelée.

Le supersampling concerne les rayons de 3 à 48 pixels, ou 3 à 24 en qualité réduite.
La plus grande surface temporaire de cercle fait 200×200 pixels. Le cache contient
au maximum 48 entrées et 250 000 pixels, réduits à 24 entrées et 100 000 pixels.
Les clés comprennent couleur/alpha, rayon et épaisseur, jamais la position ; les
cercles identiques de plusieurs systèmes réutilisent la même image. Les transformations
des sprites, les caches des planètes, les halos et les graphismes améliorés restent actifs.

Une erreur SDL connue dans l'option de supersampling provoque un repli vers draw.circle.
Une erreur sur la surface cible, une allocation ou une transformation inattendue remonte
normalement : elle n'est pas assimilée à un succès de rendu.

## Vérifications autorisées et exécutées

Tests uniquement simulés, sans import Pygame, rasterisation réelle, fenêtre ou audio.
Treize nouveaux tests couvrent : gfxdraw importable mais inutilisable, comportement PC
fonctionnel, absence d'appel gfxdraw sur Web, erreur connue signalée une seule fois,
erreurs inattendues propagées, aaline absent/défaillant, line/polygon/ellipse avec RGBA,
surfaces alpha, panneaux/halos/planètes et masque, cache et tailles bornés, échec de
smoothscale et erreur de blit de la cible.

La suite de régression conserve les tests de campagne, batailles, économie, sauvegardes
et LAN. Les connexions de test LAN existantes restent limitées à 127.0.0.1 dans le même
processus de tests. Aucune partie n'a été lancée et les assets n'ont pas été modifiés.
Résultat final : **250 tests réussis**, aucune erreur, aucun test ignoré ; analyse statique
de 69 fichiers Python sans erreur, syntaxe JavaScript contrôlée sans exécution DOM.
Résultats machine : `docs/LOGIC_TESTS_0_4_1.json` et `docs/PYTHON_STATIC_CHECKS.json`.

**Cette correction n'est pas déclarée vérifiée dans Opera GX.** Le succès Chromium du
correctif de démarrage précédent ne couvrait que le menu et ne prouvait pas le rendu de
la galaxie. Le test distant préparé dans le workflow ouvre désormais Nouvelle campagne,
attend le signal envoyé seulement après une frame galactique dessinée et produit
`galaxy.png`. Ce workflow n'est pas déclenché pendant cette intervention : les essais
graphiques restent manuels conformément à la demande actuelle.

## Déployer et tester manuellement

1. GitHub → Actions → **STAR ARENA Web Edition** → **Run workflow**, branche `main`.
2. Attendre build, contrôle d'archive, test distant menu/galaxie puis deploy.
3. En cas d'échec, lire l'artefact `web-startup-diagnostics` : `console.json`, `result.json`,
   `menu.png` et `galaxy.png` lorsqu'ils ont été produits.
4. Dans Opera GX, ouvrir le site puis Ctrl+F5, créer une campagne et vérifier carte,
   zoom, navigation souris, sélection, halos, planètes et bataille. Tester F7 dans les
   deux profils visuels. Les sauvegardes et paramètres existants sont conservés.

Fichiers principaux : `presentation/art.py`, `renderer.py`, `battle_renderer.py`,
`tests/test_graphics_compat.py`. Le signal de frame dans `app.py` et `web/browser.js`,
le script CI et le nom d'étape du workflow assurent la future vérification de la galaxie.
Le moteur, les statistiques, le réseau et les formats de sauvegarde sont inchangés.
