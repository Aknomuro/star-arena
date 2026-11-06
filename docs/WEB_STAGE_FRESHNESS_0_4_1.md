# V0.4.1 — comparaison origin/main, staging et site publié

## Constat réel avant correction du staging

Le 6 novembre 2026, vérification sans navigateur :

| Emplacement | Résultat |
| --- | --- |
| HEAD local | `c5bb6a9934ebc44b695236368a07d6e812d4af10`, correctif gfxdraw présent. |
| origin/main, lu avec ls-remote | Même commit ; fichier art.py public identique au local après normalisation des fins de ligne. |
| `web_build/arena/src/star_arena/presentation/art.py` | Ancienne copie avec `gfx.aacircle(surface, *xy, r, color)` sans protection. |
| Archive Pages lue par HTTP | `assets/star_arena/presentation/art.py` contient encore ce même appel non protégé ; ancienne version toujours déployée. |

Empreinte SHA-256 de l'ancien `art.py` effectivement servi :
`035ee48a49ad801cf64fe8514657e4324ca741c6abc519d64d8ff4828ff362c4`.

Cela montre une différence entre code publié dans Git et jeu déployé sur Pages, et non
la persistance de cet appel non protégé dans le correctif c5bb6a9. Un push Git n'exécute
pas notre workflow manuel ; relancer un ancien run réutilise aussi son ancien commit.

## Préparation réellement corrigée

L'ancien dossier local `web_build/arena` a été conservé intégralement sous
`web_build/stage_history/arena-20261106T194334Z-3b1e34f7`, puis un nouveau dossier a été
créé depuis les sources corrigées. Les 59 fichiers ont été comparés octet par octet.
Le staging actif n'a plus l'ancien préfixe `src/`, ni les anciens résultats de compilation.
Aucun fichier personnel ou ancien fichier de jeu n'a été supprimé.

Le fichier actif `web_build/arena/star_arena/presentation/art.py` correspond exactement
à `src/star_arena/presentation/art.py`. SHA-256 local et staging :
`3658b5ea6ad87bea0d043debf1ab9ef9d4fd927b9f768c751bf16eb6f80ac142`.
Ces empreintes décrivent les octets vérifiés localement ; les fins de ligne peuvent être
normalisées par Git. Chaque compilation recalcule les empreintes réelles de son archive.

## Garde-fous ajoutés

- `prepare_web.py --stage web_build/arena --refresh` conserve l'ancienne copie hors du
  dossier compilé, puis recrée le paquet autorisé. Cette option refuse les destinations
  non canoniques, liens externes et jonctions ; source et destination du déplacement
  sont résolues et vérifiées dans `web_build` avant toute opération.
- `prepare_web.py --verify-stage web_build/arena` compare la liste et les octets de tous
  les fichiers aux sources actuelles. Tout ancien art.py, fichier manquant ou supplémentaire
  bloque la compilation. Le workflow le lance immédiatement avant Pygbag.
- Le contrôle après build conserve sa comparaison exacte des membres de l'archive aux
  sources, et ajoute la vérification des empreintes dans `build-info.json`.
- `build-info.json` contient désormais `source_commit`, `package_sha256` et `art_sha256`.
  L'empreinte de art.py est calculée depuis l'archive, pas supposée depuis le fichier source.
- Le rendu possède un garde-fou supplémentaire à chaque appel de `Painter.circle` :
  sous Emscripten, aucun Painter ne peut appeler gfxdraw, même s'il avait été créé avant
  le changement de contexte. Le repli draw.circle et l'anticrénelage local borné sont conservés.

Les autres primitives gfxdraw ne sont pas utilisées. L'import facultatif desktop et son
repli ciblé restent couverts par les tests du correctif précédent. Les primitives draw
et les erreurs inattendues conservent leur comportement documenté.

## Tests et limites

256 tests légers réussis, aucun import Pygame ni fenêtre. Nouveaux cas : Painter réutilisé
en contexte Web, staging périmé refusé, sauvegarde intégrale de l'ancien staging (y compris
un fichier privé simulé), cible de rafraîchissement non autorisée, archive avec ancien art.py
refusée malgré des métadonnées de provenance recalculées. Les tests qui font réellement
échouer le faux gfxdraw.aacircle restent présents dans `tests/test_graphics_compat.py`.

Aucune compilation Pygbag, installation, exécution de jeu ou test navigateur n'a été lancé
pendant cette intervention. Le staging est régénéré et vérifié ; il n'est pas présenté comme
un build Web nouvellement déployé. Les anciennes données personnelles restent ignorées par Git.

## Déploiement de la version corrigée

1. GitHub → Actions → **STAR ARENA Web Edition → Run workflow**, branche **main**.
   Créer un nouveau run ; ne pas utiliser Re-run sur un ancien commit.
2. Vérifier dans le run le hash affiché et attendre build, test menu/galaxie, puis deploy.
3. Après succès, consulter `https://aknomuro.github.io/star-arena/build-info.json` et
   vérifier que `source_commit` correspond au commit choisi dans ce nouveau run.
4. Ouvrir le jeu dans Opera GX, Ctrl+F5, puis Nouvelle campagne. En cas de problème,
   relever le traceback et les diagnostics du nouveau run, avec son commit.

Les règles de jeu, statistiques, sauvegardes, assets source et multijoueur PC sont préservés.
