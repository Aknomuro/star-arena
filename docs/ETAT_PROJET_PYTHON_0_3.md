# État du projet Python — V0.3.0

> Rapport historique de la V0.3.0 initiale (81 tests à sa livraison). L’extension actuelle,
> son format JSON 4 et ses nouveaux résultats sont décrits dans `ETAT_PROJET_PYTHON_0_3_DEFENSES.md`.

Date : 5 novembre 2026. Mise à jour « Galactic Expansion & Shipbuilding ».

La V0.3.0 est implémentée dans le projet existant. La logique est validée par les tests ci-dessous.
Le jeu et les interfaces graphiques n'ont pas été lancés : cette livraison ne constitue pas une
validation visuelle ni une déclaration de stabilité complète.

## Fonctionnalités livrées

- Nouvelles campagnes de 60 systèmes, graine reproductible, identifiants stables, noms distincts,
  richesses de 1 à 4, routes de voisinage connectées et passages entre rangées limités.
- Trois capitales éloignées. API de génération pour 15, 30, 60 et 100 systèmes ; le choix de taille
  dans le menu reste une extension future conformément à la demande.
- Caméra bornée par la carte réelle, zoom minimum 0,12, bouton de recentrage sur une capitale
  contrôlée et mini-carte informative montrant factions, routes et centre de caméra.
- Stocks par faction : 600 crédits et 350 minerais au départ. Chaque système contrôlé produit
  4 crédits/s ; sa richesse produit respectivement 0, 2, 4 ou 6 minerais/s.
- Revenus et production par pas économique d'une seconde, dans la simulation existante à pas fixe.
  Pause, menus, perte de focus et engagements bloquent la campagne. ×2 et ×4 accélèrent ensemble
  économie, files et déplacements. Le rattrapage après blocage reste volontairement borné.
- Chantiers de niveaux 1 à 3, construction et améliorations payantes immédiates, coûts centralisés
  dans `systems/economy.py`. Déblocages chasseur / corvette / croiseur selon le niveau.
- Achat payé à l'ajout, file séquentielle de 20 commandes maximum. Fin de production : unité réelle,
  statistiques existantes, identifiant monotone et unique, coque et bouclier complets. Une flotte
  alliée immobile reçoit l'unité ; en son absence, une flotte est créée.
- Conquête : niveau du chantier conservé, ancienne file annulée sans remboursement. Aucun achat
  refusé ne débite de ressources. Une fusion déplace les références des unités sans les recréer.
- Gestion de base des flottes : détacher le dernier vaisseau dans une nouvelle flotte, transférer
  le dernier vaisseau ou fusionner toute la flotte vers la première autre flotte alliée immobile
  du même système. La composition et les déplacements utilisent les unités réelles.
- IA économique : mêmes achats et délais que le joueur, jusqu'à deux sites de production,
  améliorations et alternance des classes disponibles. IA militaire : conquête et attaques
  conservées, priorité à certains sites industriels menacés et maintien d'une petite garnison.
- Panneaux français économie / flottes, stocks et revenus, prix, délais, niveaux requis,
  pagination de toute la file, progression, sortie estimée incluant l'attente, aperçu des flottes
  et notifications dans le journal.
- Format JSON 3 : carte, ressources, revenus validés, chantiers, niveaux, files, progressions,
  fraction économique, compteurs d'identifiants, flottes, déplacements, engagements et rapports.
- Migration compatible des formats 1 et 2 : carte et unités conservées, économie initialisée,
  richesse déterministe si absente, aucun vaisseau ajouté. Le chargement ne réécrit rien.
  Enregistrement d'un ancien format : copie `.v1.bak` / `.v2.bak`, numérotée si nécessaire,
  avant remplacement atomique. Sauvegardes incompatibles ou corrompues refusées et préservées.
- Neuf PNG, caches, rotation, proportions et secours vectoriel conservés. Statistiques d'armes,
  hitboxes et règles de bataille inchangées. Le seul ajustement au combat est la gestion de
  l'ancienne file lors d'un changement de propriétaire.

## Vérifications exécutées

Un seul processus de tests de logique à la fois, Python 3.12.14, sans installation de dépendances,
sans Pygame, sans affichage et sans audio. Résultat final : **81 tests, 0 échec, 0 erreur,
0 ignoré**, en environ 0,18 seconde. Les 64 régressions précédentes sont incluses.
Preuve : `docs/LOGIC_TESTS_0_3_0.json`.

Les anciens tests utilisent explicitement leurs cartes de 15 systèmes pour préserver les cas
V0.2 ; les nouveaux tests contrôlent le défaut de 60 systèmes et les autres tailles prévues.

| Demande | Statut | Vérification réalisée |
|---|---|---|
| Galaxie de 60 systèmes connexe | OK | Parcours du graphe pour 15, 30, 60 et 100 ; comparaison complète de deux générations à graine identique ; changement avec une autre graine |
| Capitales éloignées | OK | Trois capitales, toutes les distances entre paires supérieures à 1 200 unités sur la carte par défaut |
| Identifiants uniques | OK | Unicité des unités initiales, puis contrôles de production et de transferts |
| Revenus augmentant les stocks | OK | Pas fractionné 0,4 + 0,6 seconde : aucun revenu anticipé, puis versement exact |
| Pause bloquant l'économie | OK | Porte d'entrée utilisée par l'application : campagne inchangée en pause, menu et perte de focus ; file également inchangée |
| Vitesses ×2 et ×4 | OK | Temps et stocks exacts sur trois simulations ; accélération réelle de la file via l'application sans backend graphique |
| Construction de chantier | OK | Paiement et niveau 1, propriétaire contrôlé exigé |
| Améliorations | OK | Niveaux 1 à 3, refus du niveau 4 sans débit |
| Coûts et conditions des vaisseaux | OK | Refus faute de minerais/crédits ou de niveau, conservation des stocks refusés |
| File de production | OK | Deux commandes terminent l'une après l'autre ; plafond 20 et refus de propriétaire adverse sans mutation |
| Affectation à une flotte | OK | Réception sur place et création d'une flotte si aucune n'est disponible |
| Identifiants de production | OK | Identifiants supérieurs aux initiaux et non réutilisés après destruction des unités produites |
| Fusion sans duplication | OK | Détachement, transfert partiel puis fusion : mêmes objets, identifiants, coques et boucliers |
| Production par les IA | OK | 250 secondes simulées avec déplacements isolés : IA produit les trois classes et paie effectivement ses achats |
| Nouvelles unités en RTS | OK | Unité produite retrouvée dans le moteur tactique avec la même référence ; régressions de dégâts et résolution conservées |
| Sauvegardes économie et constructions | OK | Production achevée, seconde commande partielle et voyage ; sauvegarde/recharge sur disque, égalité complète puis continuation identique |
| Anciennes sauvegardes | OK | Fichiers V1 et V2 sans champs économiques migrés, relus et archivés à l'identique avant enregistrement V3 |
| Conquête et validation économique | OK | Annulation d'une file ennemie et rejet d'un stock négatif dans le JSON |
| Régressions V0.2/V0.2.1 | OK | Batailles, dégâts, réserves, arrivées simultanées, contrôles simulés, sauvegardes et pipeline de sprites : anciens tests conservés |
| Analyse statique | OK | 31 fichiers Python, 74 imports locaux et 160 symboles vérifiés ; aucune erreur ; séparation données/simulation/rendu préservée |
| Assets PNG | OK pour les fichiers | Neuf PNG présents, neuf correspondances, neuf SHA-256 conformes au manifeste, aucun asset manquant ; inspection légère des en-têtes sans décodage |
| Affichage et clics Pygame | NON TESTÉ | Aucun lancement graphique autorisé ; validation manuelle nécessaire |
| Équilibrage et longue campagne interactive | NON TESTÉ | Tests courts de logique uniquement |

Les erreurs transitoires des premiers passages de tests concernaient la migration des métadonnées
introduites sur les fixtures V2 et la synchronisation du propriétaire de chantier. Elles sont
corrigées ; le résultat final ci-dessus est celui de la dernière suite. Les archives des vrais
fichiers de sauvegarde du joueur n'ont pas été modifiées par ces tests.

## Fichiers créés ou modifiés

- `src/star_arena/domain/models.py` : ressources, richesses, chantiers, commandes et compteurs.
- `src/star_arena/domain/galaxy.py` : génération étendue et tailles configurables par l'API.
- `src/star_arena/systems/economy.py` : économie active, coûts, chantiers, production, transferts et IA.
- `src/star_arena/systems/simulation.py` : branchement économique et priorités défensives.
- `src/star_arena/systems/combat.py` : annulation des anciennes commandes lors d'une conquête.
- `src/star_arena/persistence.py` : format 3, validation, migration et archives des anciens formats.
- `src/star_arena/app.py` : commandes économiques, gestion de flottes, caméra et progression testable.
- `src/star_arena/presentation/renderer.py` : barre économique, panneaux, file, mini-carte et boutons.
- `src/star_arena/presentation/camera.py` : plage de zoom étendue.
- `src/star_arena/config.py` : version du format de sauvegarde.
- `src/star_arena/__init__.py`, `pyproject.toml` : version 0.3.0.
- `tests/test_expansion.py` : 17 nouveaux tests.
- `tests/test_warfare.py`, `tests/test_extremes.py` : taille historique explicite des fixtures.
- `README.md`, `AGENTS.md` : documentation et état courant.
- `docs/ETAT_PROJET_PYTHON_0_3.md` : présent rapport.
- `docs/LOGIC_TESTS_0_3_0.json`, `docs/PYTHON_STATIC_CHECKS.json` : résultats exécutés.

Aucun PNG, fichier Godot ou archive existante n'a été supprimé ou remplacé.

## Limites et validation manuelle

Le rendu et les interactions doivent encore être testés sur le PC de l'utilisateur. La gestion
actuelle transfère le dernier vaisseau vers une destination alliée déterministe ; un sélecteur
arbitraire de plusieurs unités et de destination n'est pas livré. La mini-carte est informative,
le zoom et le glissement restent les moyens d'exploration. Le menu ne propose pas encore les
quatre tailles. Il n'y a pas d'annulation/remboursement de commande ni de sauvegarde tactique
en cours de combat. L'IA économique reste volontairement simple ; sa stratégie à long terme
n'a pas été évaluée en partie graphique.

Pour valider manuellement : lancer `main.py` dans l'environnement existant, démarrer une nouvelle
campagne, explorer la carte et recentrer la capitale, construire/améliorer un chantier, produire
les trois classes, consulter la file, tester pause et ×2/×4, détacher/transférer/fusionner sur place,
déplacer une flotte produite vers un conflit, terminer le RTS puis sauvegarder et recharger.
Vérifier également les prix lisibles, la sélection des systèmes et les clics aux limites des panneaux.
