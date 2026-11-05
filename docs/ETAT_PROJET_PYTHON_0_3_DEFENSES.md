# STAR ARENA Python — V0.3.0 : systèmes planétaires, défenses et milices

Date : 5 novembre 2026. Extension de la V0.3.0 existante ; version applicative conservée à 0.3.0,
format de sauvegarde passé de 3 à **4**.

## Audit du socle et intégration

Le projet possédait déjà une galaxie de 60 systèmes, trois factions, des flottes à unités
persistantes, les voyages, le RTS, la conquête, les crédits/minerais, les chantiers de niveaux
1 à 3, leurs files, les transferts et les sauvegardes migrables. Ces systèmes sont réutilisés.
Les 81 tests précédents restent dans la suite. Aucun second moteur de combat ou de production
navale n'a été ajouté. Les neuf PNG n'ont pas été modifiés.

## Fonctionnement livré

### Planètes et vue détaillée

Chaque système contient de 1 à 5 planètes générées avec une graine locale déterministe.
Les identifiants `système × 10 + index + 1` restent stables. Noms, types, population abstraite,
richesse, propriétaire et capacité de 2 à 6 emplacements au sol sont conservés en JSON.
Le propriétaire initial correspond à celui du système. Les types sont rocheuse, désertique,
glacée, océanique, gazeuse et industrielle ; ils déterminent la richesse initiale et certaines
restrictions. Les géantes gazeuses refusent mines, industrie et installations militaires au sol.

Un clic sélectionne le système, un double-clic en moins de 350 ms ou le bouton « Vue détaillée »
l'ouvre sans recharger ni modifier la campagne. Molette : zoom ; glissement du milieu : caméra ;
clic planète : informations ; Échap : galaxie. La simulation continue, avec les mêmes règles de
pause, focus et vitesses. Un engagement ramène à la carte pour choisir RTS ou résolution abstraite.

La vue vectorielle comprend étoile, orbites et planètes, marqueurs d'installations, panneau par
planète et catégories ÉCO. / DÉFENSE / PROD. / MILICES. Les informations détaillées de développement
sont réservées aux planètes contrôlées sans occupation. Le panneau de production réutilise le
chantier et sa file existants. Les commandes donnent les coûts, délais et niveaux ; les files
planétaires sont paginées, et les installations affichent leurs dégâts et leurs effets de soutien.
L'affichage et les clics réels restent à tester par l'utilisateur.

### Constructions au sol

Les emplacements sont réservés dès la commande, y compris les travaux encore en attente.
Chaque type prend un emplacement et peut atteindre le niveau 3. Une seule commande du même
type peut être en attente. Les travaux d'une planète sont séquentiels. Les améliorations coûtent
et durent la valeur de base multipliée par le niveau acheté.

| Bâtiment | Crédits / minerais de base | Temps de base | Effet par niveau |
|---|---:|---:|---|
| Mine | 120 / 65 | 15 s | +2 × richesse minerais/s si alimentée |
| Centrale | 100 / 45 | 12 s | +6 énergie locale |
| Centre commercial | 140 / 50 | 18 s | +3 crédits/s si alimenté |
| Industrie | 200 / 100 | 24 s | +2 crédits/s ; chantier naval +15% si alimenté |
| Centre de recrutement | 110 / 40 | 15 s | Résistance +1 |
| Caserne | 160 / 70 | 20 s | Résistance +3 |
| Garnison planétaire | 220 / 100 | 25 s | Résistance +5 |

Les revenus de base des systèmes sont conservés une seule fois. Les planètes n'ajoutent un
revenu qu'avec les bâtiments correspondants ; leur population ne duplique pas le revenu du système.
La production et les coûts restent dans le pas économique d'une seconde, indépendant du rendu.

Énergie locale : base de 3, plus centrales, moins niveaux de mines et industries, moins niveaux
d'installations orbitales vivantes. Un bilan négatif divise par deux les bonus économiques et la
vitesse des travaux planétaires ; l'industrie n'accélère plus le chantier naval. Le stock
énergétique affiché est le cumul du bilan de faction, borné à zéro ; l'alimentation et ses
conséquences sont décidées localement. L'entretien orbital est retiré des revenus de crédits ;
les stocks restent bornés à zéro. Aucun achat refusé ne débite les ressources.

### Stations et défenses

Une planète dispose d'un emplacement principal de station. Les défenses indépendantes ont
2 emplacements au départ, 3 avec une station de niveau 2/3 et 4 au niveau 4. Les emplacements
occupés par une épave restent réservés à cette installation jusqu'à sa reconstruction.

| Station | Coque | Bouclier | Tourelles | Milice maximale | Réparation coque/s | Entretien crédits/s | Coût C/M | Délai |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| Avant-poste N1 | 1 400 | 600 | 2 | 2 chasseurs | 1 | 1 | 300 / 150 | 30 s |
| Station militaire N2 | 2 600 | 1 200 | 4 | 4 chasseurs | 2 | 2 | 500 / 260 | 45 s |
| Forteresse N3 | 4 300 | 2 200 | 6 | 6 chasseurs + 1 corvette | 4 | 3 | 800 / 430 | 65 s |
| Citadelle N4 | 6 500 | 3 600 | 8 | 10 chasseurs + 2 corvettes | 6 | 4 | 1 200 / 650 | 90 s |

Les niveaux sont obligatoirement successifs. La validation JSON refuse une commande sautant
les niveaux. Une amélioration conserve les proportions de coque et de bouclier restantes ;
elle ne soigne pas gratuitement la station. Une station détruite peut être reconstruite à
son niveau antérieurement acquis, au coût et délai complets de ce niveau.

| Installation indépendante | Coût C/M | Temps | Utilité réelle |
|---|---:|---:|---|
| Plateforme laser | 160 / 80 | 20 s | Dégâts ×2,5 contre les chasseurs |
| Batterie de missiles | 240 / 120 | 28 s | Dégâts ×2,4 contre corvettes et croiseurs |
| Tourelle lourde | 280 / 150 | 30 s | Dégâts ×1,5 contre les cibles autres que chasseurs |
| Générateur de boucliers | 230 / 130 | 26 s | +12 bouclier/s aux alliés vivants à portée |
| Station de réparation | 210 / 100 | 24 s | +8 coque/s aux alliés vivants à portée |
| Relais radar | 150 / 70 | 18 s | Acquisition plus fréquente et +20% portée aux alliés proches |

Chaque défense indépendante coûte un crédit/s d'entretien. Ces installations ont actuellement
un seul niveau ; les améliorations concernent les bâtiments au sol et les stations principales.
Les statistiques et les coûts sont centralisés dans `domain/planet_stats.py`.

Chaque installation possède un identifiant, une coque, un bouclier, des armes et une portée.
Elle apparaît physiquement comme unité immobile dans le RTS ; la position est attribuée au
déploiement tactique, et la coque construite reste le même objet pendant le combat. Les neuf
sprites de vaisseaux sont conservés ; les installations utilisent des silhouettes vectorielles
avec libellé et barres d'état. Elles sont prioritaires sur les réserves de grandes flottes afin
que les stations construites apparaissent dès le début, sans dépasser le plafond tactique.

Un système sans flotte mobile mais avec une station déclenche bien un engagement lorsqu'il est
attaqué. La résolution automatique utilise les mêmes unités, coques, armes, milices et pertes.
Elle reste abstraite : réparation/boucliers portent sur le camp, le radar donne +10% de dégâts
plutôt qu'une trajectoire ou une portée spatiale. La géométrie du RTS n'est pas simulée dans
cette résolution. Une installation détruite conserve sa coque nulle et ne réapparaît pas
spontanément. La reconstruction est une nouvelle commande payante avec un nouvel identifiant.

### Milices, occupation et production navale

Les statuts `permanent`, `militia` et `orbital` sont explicites sur les unités. Les garnisons
n'existent comme flotte technique que pendant un engagement ; elles sont ensuite retirées,
tandis que les unités restent liées à leur planète. Elles ne peuvent ni voyager ni être
transférées ou fusionnées dans une flotte permanente. Les survivants gardent leurs dégâts.
Une validation de sauvegarde empêche le détournement des identifiants dans des flottes mobiles.

La reconstitution produit une unité à la fois : 20 secondes et 25 C/10 M par chasseur ;
35 secondes et 60 C/30 M par corvette. Elle nécessite une station vivante et des ressources,
ne dépasse pas sa capacité et ne ressuscite pas les anciens identifiants. Le délai commence
après la fin de construction de la station ; la sortie d'une bataille réinitialise l'horloge.
Les milices ne sont ni vendables ni transférables. Une défaite orbitale supprime les milices
restantes du camp perdant et détruit ses installations encore vivantes ; elles ne se replient pas.

Le vainqueur spatial contrôle le système, mais une planète ennemie avec résistance conserve
son ancien propriétaire pendant `10 + 5 × résistance` secondes d'occupation. Il faut une flotte
permanente immobile du vainqueur sur place pour faire avancer ce délai. Les bâtiments ne produisent
pas pendant l'occupation et les commandes précédentes sont annulées sans remboursement. Sans
résistance, le transfert est immédiat. Le retour du précédent propriétaire annule le siège.
Aucun combat terrestre jouable ou fictif n'est créé.

Le chantier naval conserve ses classes, coûts, niveaux et files. Les sorties sont toujours
des unités permanentes, affectées à une flotte immobile du système ou à une nouvelle flotte.
L'engagement orbital gèle toute la campagne et ses productions ; celles qui restent contrôlées
reprennent ensuite. Les industries alimentées accélèrent la production navale. Les navires
et installations ne sont pas reconstruits gratuitement par le retour à la galaxie.

### IA et sauvegardes

Les IA développent jusqu'à trois systèmes prioritaires, avec préférence aux capitales ; elles
construisent stations, alimentation, mines, casernes et défenses de frontière, puis améliorent
les stations. Un emplacement refusé ne bloque pas les autres choix possibles. Les commandes
utilisent exactement la validation et les débits du joueur. La production navale antérieure
est conservée. L'évaluation des attaques inclut désormais la puissance des installations et
milices persistantes du défenseur.

Le format JSON 4 conserve tous les nouveaux champs, dégâts, identifiants, horloges, constructions,
files et occupations. Lors d'une recharge avant combat, les unités de la garnison technique sont
reliées aux mêmes objets que les défenses et milices planétaires : aucune copie combattante
supplémentaire n'est créée.

Les formats 1/2/3 compatibles sont lus. Les planètes absentes sont générées avec le propriétaire
existant, sans station, bâtiment ou milice gratuite. Les données économiques et files du format 3
restent conservées. Le chargement n'écrit rien. L'enregistrement crée une copie de l'ancien fichier
`.v1.bak`, `.v2.bak` ou `.v3.bak` (numérotée si nécessaire) avant remplacement atomique. Les formats
incompatibles sont refusés. La sauvegarde en plein RTS reste interdite, comme dans le socle précédent.

## Tests exécutés et résultats

**106 tests réussis, 0 échec, 0 erreur, 0 ignoré**, dont 81 régressions et 25 nouveaux tests
planétaires. Dernière exécution : Python 3.12.14, environ 0,68 seconde, un seul processus léger.
Aucun import de Pygame, aucune fenêtre, aucun audio. Preuve : `docs/LOGIC_TESTS_0_3_0.json`.

| Demande | Statut | Vérification |
|---|---|---|
| 1 à 5 planètes / système | OK | Parcours de la génération, tailles et propriétaires initiaux ; égalité de deux campagnes à graine identique |
| Identifiants uniques | OK | Ensemble des identifiants planétaires ; unités produites, reconstruction et régression des flottes |
| Ouverture sans altérer la campagne | OK logique | Même simulation et égalité complète des données avant/après ouverture et retour ; sélection géométrique d'une planète |
| Limites de construction | OK | Emplacements réservés dès la commande, refus de dépassement au sol et en orbite sans mutation |
| Coûts et délais | OK | Débits exacts, absence de bâtiment avant échéance, amélioration plus longue et restriction des géantes gazeuses |
| Stations successives | OK | Niveaux 1 à 4, délai du niveau 1, refus d'une seconde commande et du niveau 5 ; JSON sautant les niveaux refusé |
| Création de milices | OK | Délais après construction, coûts, statuts et effectifs bornés |
| Absence de duplication | OK | Déploiement répété sans deuxième garnison ; refus voyage/transfert ; renouvellement après perte avec nouvel identifiant |
| Destruction persistante | OK | Dégâts RTS, plateforme détruite, fin de combat, sauvegarde/recharge, attente puis reconstruction payante |
| Présence physique des stations | OK logique RTS | Même objet dans le moteur tactique, coordonnées immobiles malgré un ordre ; priorité de déploiement avec une grande flotte |
| Bataille contre station sans flotte | OK | Arrivée hostile dans un système dont la flotte est vide : engagement incluant la station |
| Résolution automatique avec défenses | OK | Défenses incluses, état appliqué et garnison temporaire supprimée sans duplication |
| Économie planétaire | OK | Bonus de mine/commerce ajoutés une seule fois, pénurie réduisant la production, centrale rétablissant l'alimentation |
| Construction navale préservée | OK | Vaisseau livré à une flotte permanente ; tests antérieurs des trois classes et de leurs coûts conservés |
| Occupation après victoire | OK | Résistance, ancien propriétaire temporairement conservé, pause sans flotte, reprise avec présence et transfert final |
| Sauvegarde / recharge | OK | Planètes, dégâts, siège et engagement rechargés ; références d'unités partagées rétablies et dégâts appliqués après recharge |
| Migration V3 | OK | Ancien fichier sans planètes migré sans défense gratuite, puis archive `.v3.bak` identique à l'original |
| IA stratégique | OK pour la logique testée | Débit, commande différée puis station achevée ; IA économique précédente continue à produire les trois classes |
| Soutiens tactiques | OK | Réparation de coque et régénération du bouclier observées ; radar augmentant la portée effective d'un tir ; spécialisations laser/missiles |
| Combat RTS naturel | OK sans rendu | Station construite contre un chasseur : combat simulé jusqu'à victoire, résultat appliqué une seule fois |
| Pause / vitesse en vue système | OK logique | Construction inchangée en pause, puis temps de construction réduit exactement par ×4 |
| Contrôle statique | OK | 36 fichiers Python, 107 imports locaux, 248 symboles ; aucune erreur ; simulation/données sans Pygame |
| Assets préservés | OK fichiers | 9 PNG, 9 emplacements dédiés, 9 empreintes SHA-256 identiques au manifeste ; aucun fichier manquant |
| Rendu et événements Pygame réels | NON TESTÉ | Aucun lancement graphique : validation manuelle nécessaire |
| Équilibrage d'une longue campagne | NON TESTÉ | Aucun processus lourd ou partie graphique automatique |

Les premiers passages ont corrigé un index d'entretien incorrect et précisé le début du délai
de reconstitution après l'achèvement d'une station. La dernière suite ci-dessus est entièrement
passante. Les sauvegardes du joueur ne sont pas utilisées comme fichiers de test.

## Fichiers créés ou modifiés

Créés :

- `src/star_arena/domain/planet_stats.py` — données centralisées des types, bâtiments et stations.
- `src/star_arena/domain/planet_generation.py` — génération déterministe et positions de vue système.
- `src/star_arena/systems/planets.py` — constructions, effets, garnisons, milices, occupation et IA.
- `src/star_arena/presentation/system_view.py` — vue détaillée et sélection des planètes.
- `tests/test_planets.py` — 25 tests de logique.
- `docs/ETAT_PROJET_PYTHON_0_3_DEFENSES.md` — présent rapport.

Modifiés :

- `src/star_arena/domain/models.py`, `galaxy.py`, `ship_stats.py` — données et statistiques orbitales.
- `src/star_arena/systems/economy.py` — bonus, entretien, énergie et vitesse industrielle.
- `src/star_arena/systems/simulation.py` — défenses à l'arrivée, occupation et estimation militaire.
- `src/star_arena/systems/combat.py` — engagement et application des résultats aux garnisons.
- `src/star_arena/systems/tactical.py` — unités immobiles, soutien à portée et déploiement prioritaire.
- `src/star_arena/persistence.py`, `config.py` — format 4, validation et migration.
- `src/star_arena/app.py` — navigation, double-clic, commandes et simulation dans la vue détaillée.
- `src/star_arena/presentation/renderer.py`, `battle_renderer.py` — accès à la vue et dessin des installations.
- `README.md`, `AGENTS.md`, `docs/ETAT_PROJET_PYTHON_0_3.md` — état actuel et historique.
- `docs/LOGIC_TESTS_0_3_0.json`, `docs/PYTHON_STATIC_CHECKS.json` — résultats exécutés à jour.

Aucun logiciel installé. Aucun fichier Godot, archive ou PNG supprimé ou remplacé.

## Limites et validation manuelle restante

- Aucun rendu n'a été lancé : lisibilité, double-clic réel, zoom, changements de vue, limites des
  panneaux et déroulement d'une bataille visible restent à tester sur le PC de l'utilisateur.
- La reconnaissance est simple : informations de développement masquées hors contrôle, mais
  absence de brouillard de guerre complet sur les noms et types de planètes.
- Population abstraite fixe, pas de croissance démographique ni de terrain jouable.
- Un exemplaire de chaque défense indépendante par planète ; son emplacement est réservé même
  détruit. Seuls les bâtiments au sol et la station principale ont plusieurs niveaux.
- Pas de démolition, déplacement d'installation ou remboursement de commande dans cette version.
- Les positions orbitales sont générées au déploiement tactique ; pas d'éditeur de placement libre.
- Les soins actifs agissent en bataille, pas comme réparation automatique des épaves en campagne.
- L'IA reste heuristique ; les longues campagnes et l'équilibrage des citadelles restent à évaluer.
- La résolution automatique reste une abstraction sans géométrie, décrite ci-dessus.

Test manuel recommandé : ouvrir un système par double-clic, choisir une planète contrôlée,
commander une station et une plateforme, contrôler les débits et délais, subir une attaque,
vérifier les silhouettes et les soutiens en RTS, terminer le combat puis sauvegarder/recharger
pour vérifier les dégâts. Contrôler également la reconstitution payante, les sièges et les files
pendant pause, ×2 et ×4. La V0.3.0 n'est pas déclarée stable graphiquement à ce stade.
