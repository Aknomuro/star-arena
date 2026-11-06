# STAR ARENA: GALACTIC CONQUEST — Python 0.4.1

**Web Edition & GitHub Pages** : adaptation Web du moteur solo et conservation du PC/LAN.

Dépôt public : [Aknomuro/star-arena](https://github.com/Aknomuro/star-arena).
Pour GitHub Pages : Settings → Pages → Source **GitHub Actions**, puis Actions →
**STAR ARENA Web Edition → Run workflow**. Utiliser l'URL retournée par le déploiement réussi.

Correctif de démarrage Web : paquet `star_arena` directement importable dans l'archive,
diagnostics avant Python/WASM et première image du menu forcée. Le workflow contrôle maintenant
le menu avec Chromium sur le runner GitHub, puis conserve sa console et une capture dans
`web-startup-diagnostics`. Aucun navigateur n'est lancé sur le PC par ces outils.
[Rapport du correctif écran noir](docs/WEB_STARTUP_FIX_0_4_1.md).
60 systèmes, économie, chantiers navals, gestion planétaire et défense orbitale.
Python 3.11+ et Pygame CE. Les batailles RTS et les neuf vrais PNG de la V0.2.1 sont conservés.

## Lancement manuel dans Visual Studio Code

La caméra suit la position de la souris dans la carte, les systèmes et les batailles : un carré
central invisible reste immobile ; en dehors, le déplacement accélère progressivement vers le bord.
Le déplacement s'arrête sur les boutons, hors de la carte, dans les menus et pendant un clic ou
une sélection. Le zoom et le glisser avec le bouton du milieu restent disponibles.

```powershell
.\.venv\Scripts\python.exe main.py
```

Sélectionner `.venv\Scripts\python.exe` dans VS Code ; le profil F5 est manuel.
Aucune fenêtre, aucun navigateur ni test graphique n'est lancé automatiquement.
Si les dépendances manquent, leur installation reste manuelle :

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## V0.4.1 : préparation de la Web Edition

Le solo utilise le même moteur sur PC et dans l'adaptation Pygbag : boucle coopérative,
stockage navigateur, import/export JSON, activation audio après interaction et barre de commandes
Web. La galaxie dispose d'un cache des routes ; les caches de sprites et de planètes, la qualité
réduite et les limites d'effets restent actifs. Le rendu Web vise 30 images/s sans attente bloquante.

Le dossier **`web_build/arena/` a été réellement préparé** : 58 fichiers, 1 286 187 octets,
dont les neuf PNG et les six WAV existants. Les sept effets sont synthétisés par le code inclus.
Les fichiers privés et le serveur LAN sont exclus. Ce dossier contient les sources et assets à
empaqueter ; **il ne contient pas encore un build navigateur exécutable**.

**220 tests de logique réussis**, sans Pygame ; contrôle statique de 63 fichiers Python sans erreur,
et syntaxe JavaScript vérifiée. Pygbag n'est pas disponible dans le Python utilisé pour ces
vérifications : aucune installation, compilation WASM, publication ou ouverture de navigateur
n'a été effectuée. La version Web n'est donc pas déclarée jouable ou stable dans un navigateur.

Pour publier après avoir envoyé ces fichiers dans votre propre dépôt GitHub :

1. Dépôt → **Settings → Pages → Build and deployment → Source : GitHub Actions**.
2. **Actions → STAR ARENA Web Edition → Run workflow**, sur la branche contenant cette version.
3. Attendre les jobs `build` et `deploy`, puis ouvrir l'URL indiquée par GitHub dans le résultat.

Le workflow est manuel et construit seulement le paquet isolé ; aucun dépôt ni lien public n'a
été inventé. Les chemins du jeu sont relatifs, adaptés à un site de projet tel que `/star-arena/`.
La première Web Edition est solo ; le bouton affiche **Multijoueur Web en préparation**.
Le PC garde son multijoueur LAN et ses fichiers JSON habituels.

Dans le navigateur : **Sauver**, **Charger**, **Exporter JSON** et **Importer JSON** sont dans la
barre au-dessus du canvas. Sauver utilise `localStorage` séparément des préférences audio.
Importer charge en mémoire sans écraser la sauvegarde locale. Les erreurs de quota ou de stockage
sont affichées ; l'export reste disponible. Exporter régulièrement : navigation privée, effacement
des données du site, changement de navigateur ou de domaine peuvent rendre le stockage inaccessible.
Terminer la bataille RTS avant une opération de sauvegarde/import/export.

[Rapport V0.4.1, publication et test manuel Chrome/Edge](docs/WEB_EDITION_0_4_1.md).
[Procédure de build Pygbag et GitHub Pages](web/README.md).

## V0.4.0 : multijoueur hébergé par un joueur

**Campagne PC/LAN à 2 ou 3 joueurs**, une faction différente par personne. L'hôte fait tourner
la seule simulation ; tous les affichages, y compris le sien, reçoivent les instantanés du serveur.
Aucun serveur central permanent et aucune dépendance supplémentaire à installer.

**Limite de cette première livraison : les batailles multijoueurs sont résolues automatiquement
par l'hôte. Le RTS interactif reste réservé au solo. WebRTC et clients navigateur ne sont pas livrés.**
Les flottes, stations, milices, dégâts, conquêtes et résultats sont pris en compte par la résolution
existante. Les autres participants attendent le résultat commun, sans calculer leur propre bataille.

Pour jouer sur le même réseau :

1. Les deux PC lancent cette même version du jeu avec la commande de lancement ci-dessus.
2. Hôte : **Multijoueur PC / LAN → Créer une partie**. Saisir nom, port (8765 par défaut) et graine.
   L'écoute `0.0.0.0` permet le LAN ; choisir une IP locale précise si nécessaire. Ouvrir le salon.
3. Relever l'IPv4 du PC hôte avec `ipconfig`, puis transmettre cette IP, le port et l'invitation
   affichée dans le salon. Le bouton Copier facilite la transmission de la clé.
4. Invité : **Rejoindre / reconnecter**, saisir cette IP, le port, son nom et l'invitation.
   `127.0.0.1` désigne le PC courant : l'utiliser seulement pour deux instances sur le même PC.
5. Choisir des factions distinctes. L'hôte choisit la taille (15/30/60/100) et clique **Démarrer**.
6. Déplacer une flotte, produire des unités et développer ses planètes : l'hôte valide chaque
   commande et dépense, puis diffuse l'état commun. F10 est désactivé pour tous, y compris l'hôte.

Le jeu ne modifie ni routeur ni pare-feu. Si Windows bloque la connexion, l'autorisation réseau
privée de l'application doit être examinée manuellement. Ne pas exposer le WebSocket brut sur
Internet ; un réseau privé chiffré authentifié entre les joueurs est une piste à configurer et
valider manuellement pour une connexion distante. Aucun code de salon ne traverse les routeurs.

Si un joueur manque, la campagne est suspendue et sa faction réservée, sans reprise par l'IA.
Sa clé personnelle est conservée dans `settings/network_reconnect.json` ; rejoindre la même
adresse et le même port permet la reconnexion. Ce fichier est privé et exclu du staging Web/Git.
Si la clé est perdue, l'hôte peut réinviter cette place depuis le salon de la campagne rechargée.

L'hôte sauvegarde dans **`saves/multiplayer.json`**, séparé du solo. Le menu de session propose
**Sauvegarder puis fermer** ; fermer la fenêtre ne sauvegarde pas automatiquement. Pour reprendre :
**Héberger la sauvegarde multijoueur**, reconnecter les invités, puis **Démarrer / reprendre**.
La taille et la géométrie d'une campagne chargée restent conservées. Pas de migration d'hôte.

**198 tests réussis**, dont 24 nouveaux contrôles réseau et les 174 régressions. Les connexions
WebSocket ont été réellement testées sur boucle locale, sans fenêtre ni son ; deux PC distincts
et le parcours graphique restent à vérifier manuellement.

[Rapport réseau, instructions LAN et limites V0.4.0](docs/MULTIPLAYER_0_4_0.md).

## V0.3.3 : carte arrondie, commandes et préparation Web

Les **nouvelles campagnes** utilisent une galaxie elliptique répartie dans un disque, avec trois
capitales périphériques éloignées. Un arbre couvrant et des raccourcis locaux maintiennent la
connexion sans croisements de routes. Les sauvegardes existantes conservent positions, routes
et identifiants ; aucune ancienne carte n'est régénérée au chargement. La caméra commence sur
une vue d'ensemble adaptée ; le bouton capitale et F recentrent comme auparavant.

**Commandes corrigées** :

- Clic gauche sur un système : sélectionner ce système, sans remplacer la flotte source.
- Clic gauche sur une icône de flotte alliée ou Tab : choisir explicitement une flotte.
- Clic droit sur un système ou une icône de flotte stationnée : donner un ordre à la source.
- Destination alliée occupée : choisir déplacement, renfort séparé ou fusion avec une flotte
  précise ; le choix est paginé si nécessaire. Le jeu attend la confirmation sans changer la source.
- Fusion : uniquement à l'arrivée, même propriétaire et même système ; aucune unité recréée.
  Si la cible a quitté les lieux, le déplacement se termine sans fusion. Une fusion réussie
  sélectionne la flotte résultante. Au même système, la fusion est immédiate.
- Destination hostile : les batailles et reprises d'itinéraire existantes restent appliquées.

Les stations et plateformes tactiques sont placées autour de leur planète réelle. Les types,
noms et tailles de planètes donnent une identité au champ de bataille ; les astéroïdes sont
reproductibles par système et évitent les installations. Les planètes restent en arrière-plan,
sans collision géante ; seules les défenses construites deviennent des unités de combat.

Rendu : contours adoucis quand l'extension graphique le permet, planètes vectorielles
suréchantillonnées localement, routes fines, halos d'influence, fond spatial précalculé,
panneaux translucides et labels allégés au grand zoom. Les neuf PNG et leurs proportions restent
conservés, avec `smoothscale`, rotation et caches bornés.

**F7** bascule la qualité réduite : moins de particules/débris, rotations et tailles regroupées,
budgets de caches réduits, halos secondaires masqués. Les armes, dégâts et limites de combat
ne changent pas. Le mode est aussi accessible dans les paramètres. Sur emscripten il est
sélectionné par défaut et l'audio attend une interaction.

Préparation Web : boucle asyncio coopérative, recherche de chemin mise en cache, partition
spatiale réutilisée pour les soutiens, mini-carte/panneaux/textes/surfaces statiques en cache.
L'outil `tools/prepare_web.py` audite le périmètre et peut préparer un dossier minimal ; il
exclut les archives historiques, .venv, sauvegardes et préférences. Voir [la préparation Web](web/README.md).
**Aucun export HTML5 ni test navigateur n'a été exécuté.** La persistance durable Web et les
performances réelles restent à valider avant publication.

[Rapport V0.3.3, fichiers modifiés et limites](docs/ETAT_PROJET_PYTHON_0_3_3.md).

## V0.3.2 : itinéraires automatiques et audio corrigé

Sélectionner une flotte puis **cliquer droit sur n'importe quel système accessible**.
Le jeu calcule l'itinéraire le plus rapide avec Dijkstra, en additionnant les temps des routes
existantes. Les segments s'enchaînent seuls ; le trajet est surligné et le panneau indique
la destination, les systèmes traversés, le segment, sa progression et l'ETA en secondes simulées.
L'ETA ne comprend pas le temps des batailles. Pause et ×1/×2/×4 s'appliquent à tout le parcours.

Un nouvel ordre en vol conserve le segment déjà engagé et sa progression : la nouvelle route
commence à son arrivée, sans téléportation. Un segment engagé reste parcouru si sa route est
retirée entre-temps ; à l'étape suivante, le chemin est recalculé. Sans chemin, la flotte attend
avec l'état **Bloquée** et repart lorsque des routes redeviennent disponibles.

Les systèmes neutres ou ennemis sans défense sont traversés sans changer leur propriétaire ;
seule la destination finale est revendiquée sans combat. Une flotte ou une installation hostile
interrompt le trajet et déclenche une bataille. Les règles normales de victoire/conquête restent
applicables ; le vainqueur reprend son itinéraire au prochain pas de campagne. Une défaite annule
l'ordre et applique le repli normal. Les occupations terrestres restent indépendantes du trajet.

**Six vraies compositions WAV originales sont maintenant livrées** dans `assets/audio/music/` :
`main_menu.wav`, `galaxy.wav`, `planetary.wav`, `battle.wav`, `victory.wav`, `defeat.wav`.
Ce sont de petites ambiances synthétiques, pas des enregistrements orchestraux. Quatre boucles de
8 secondes et deux thèmes de résultat de 3,2 secondes ; PCM mono 11 025 Hz, 16 bits ; total 846 984
octets. Elles sont chargées via `pygame.mixer.music`, avec les fondus existants. Un OGG valide
fourni sous le nom correspondant reste prioritaire ; aucun OGG fictif n'a été créé.

Les effets s'adaptent désormais au format PCM 16 bits mono ou stéréo négocié avec le périphérique,
avec un cache par format. Les clics et confirmations disposent de canaux réservés ; les sons de
combat restent limités. La musique baisse temporairement pendant les effets, sans modifier vos
volumes enregistrés. Les tirs et impacts utilisent des compteurs d'événements, pour ne plus
perdre un son lorsque son projectile disparaît entre deux images.

Dans **Paramètres audio** (menu ou panneau F10), utiliser **Tester effets** et **Tester musique**.
Les volumes principal/musique/effets et activations séparées sont conservés. **F8** coupe ou
rétablit l'ensemble en respectant vos choix. Les erreurs de périphérique et le format négocié
sont affichés ; les sorties audio sont recensées au lancement manuel lorsque SDL le permet.
Les préférences restent dans `settings/audio.json`, hors des sauvegardes de campagne.

Aucune lecture réelle n'a été lancée par Codex. La présence de données PCM valides et les tests
simulés ne prouvent pas leur audibilité sur votre PC : l'écoute et le routage Windows restent
à vérifier manuellement. Voir [le rapport V0.3.2](docs/ETAT_PROJET_PYTHON_0_3_2.md).

## Cheats admin solo et effets sonores

**F10** ouvre le panneau admin en solo et suspend la simulation. Il est désactivé en multijoueur. F10 ou Échap le ferme.
Les commandes disponibles sont :

- Ajouter 10 000 crédits et 10 000 minerais à votre faction.
- Créer une flotte de 5 chasseurs, 2 corvettes et 1 croiseur dans un système sélectionné que vous contrôlez.
- Restaurer les coques et boucliers de vos unités vivantes, sans ressusciter les épaves.
- Accélérer les commandes déjà payées à une seconde par commande, séquentiellement (plus lent en pénurie).
- En RTS : éliminer les forces ennemies, y compris les réserves, et appliquer le résultat réel du combat.

Les cheats de campagne sont bloqués pendant un engagement ; le cheat de bataille est accessible
une fois le RTS ouvert. Ils sont consignés dans le journal. Les changements sont enregistrés
avec la sauvegarde manuelle habituelle ; le panneau admin ne sauvegarde pas automatiquement.

**F8** coupe ou rétablit tous les sons ; les paramètres sont aussi accessibles dans le panneau admin.
Les petits effets originaux sont synthétisés en mémoire : clic, ordre de déplacement, laser,
impact, bouclier, explosion et confirmation de production/résultat. Ils sont mis en cache,
avec un volume modéré et une limitation des répétitions. Aucun fichier audio externe ni
logiciel supplémentaire n'est nécessaire. L'audio est initialisé seulement lors du lancement
manuel du jeu, et son indisponibilité conserve un fonctionnement silencieux. Les préférences sonores sont désormais persistantes (V0.3.1). Aucun son n'a été joué automatiquement pour les vérifications.

Voir [les tests et limites admin/audio](docs/ADMIN_ET_SONS.md).

## Jouer à la V0.3.0

1. Choisir une faction puis démarrer une nouvelle campagne : 60 systèmes reproductibles, trois capitales éloignées et des territoires neutres.
2. Sélectionner sa flotte et cliquer droit sur une destination accessible : les étapes sont automatiques. Seul l’arrêt final revendique un système sans défense.
3. Les systèmes contrôlés produisent 4 crédits par seconde. Les minerais dépendent de leur richesse : 0, 2, 4 ou 6 par seconde.
4. Sélectionner un système contrôlé, construire son chantier puis cliquer sur **Produire**. Le coût est payé immédiatement ; le vaisseau rejoint une flotte alliée immobile sur place ou une nouvelle flotte à la fin du délai.
5. Améliorer le chantier pour débloquer les corvettes puis les croiseurs. Les flèches de la file permettent de consulter toutes les commandes.
6. Basculer le panneau **Flottes** pour consulter une composition, détacher le dernier vaisseau, le transférer ou fusionner vers la première autre flotte alliée immobile du même système.
7. Cliquer **Centrer capitale** pour revenir à une capitale encore contrôlée. La mini-carte montre les territoires et la position du centre de la caméra ; elle est informative.

La barre supérieure affiche les stocks et les revenus par seconde simulée. La pause, les menus,
la perte de focus et les engagements suspendent la campagne. ×2 et ×4 accélèrent voyages,
revenus et constructions ensemble. La simulation limite le rattrapage après un blocage.

| Construction | Crédits | Minerais | Durée | Niveau requis |
|---|---:|---:|---:|---:|
| Chasseur | 80 | 35 | 8 s | 1 |
| Corvette | 240 | 120 | 22 s | 2 |
| Croiseur | 700 | 380 | 55 s | 3 |

Construire le chantier coûte 200 crédits / 100 minerais ; passer au niveau 2 coûte
350 / 180 et au niveau 3 coûte 600 / 320. Ces opérations de chantier sont immédiates.
Chaque file contient au plus 20 commandes et produit un vaisseau à la fois.
Une conquête conserve le niveau du chantier et annule les commandes de l'ancien propriétaire
sans remboursement. Les mêmes coûts et délais s'appliquent aux IA, qui développent jusqu'à
deux sites industriels, améliorent leurs chantiers et alternent les classes disponibles.

Le générateur accepte déjà `new_campaign(system_count=15|30|60|100)` ; le menu crée 60 systèmes.
Les anciennes campagnes gardent leur carte existante.

## Planètes, stations et milices

Un clic sélectionne un système ; un **double-clic** (ou **Vue détaillée**) ouvre sa vue sans
recharger la campagne. Cliquer sur une planète pour la gérer, utiliser la molette pour zoomer
et Échap pour revenir à la carte. La campagne continue dans cette vue, sauf pause ou conflit.
La vue revient à la galaxie lorsqu'un engagement demande une décision.

Chaque système contient une étoile et 1 à 5 planètes déterministes : rocheuses, désertiques,
glacées, océaniques, gazeuses ou industrielles. Les informations détaillées sont réservées
aux planètes contrôlées. Les catégories **ÉCO. / DÉFENSE / PROD. / MILICES** regroupent les actions.
Les neuf PNG de vaisseaux sont conservés ; étoiles, orbites, planètes et installations utilisent
un dessin vectoriel, sans nouveaux fichiers PNG.

- **Au sol** : 2 à 6 emplacements, réservés dès la commande. Mines, centrales, commerce,
  industrie, recrutement, casernes et garnisons ; améliorations jusqu'au niveau 3.
- **En orbite** : un emplacement de station et 2 à 4 emplacements de défense selon le niveau
  de station. Avant-poste, station militaire, forteresse puis citadelle doivent être construits
  dans l'ordre, avec un coût et un délai à chaque niveau.
- **Défenses** : plateforme laser anti-chasseur, batterie de missiles anti-croiseur, tourelle
  lourde, générateur de boucliers, station de réparation et radar. Elles sont de véritables
  unités immobiles et destructibles dans les batailles. Réparation et boucliers agissent
  à portée ; le radar augmente de 20% la portée des alliés proches.
- **Milices orbitales** : générées progressivement par les stations, jamais ajoutées aux flottes
  permanentes. Un chasseur coûte 25 crédits / 10 minerais et demande 20 secondes ; une corvette
  coûte 60 / 30 et demande 35 secondes. Elles ne voyagent pas et ne se transfèrent pas.
- **Occupation terrestre abstraite** : recrutement, casernes et garnisons augmentent la résistance.
  Une victoire spatiale lance un siège de `10 + 5 × résistance` secondes si la planète est défendue.
  Une flotte permanente doit rester sur place. Aucune bataille terrestre fictive n'est créée.

Les stations endommagées conservent leurs dégâts ; les installations détruites restent des épaves
jusqu'à une reconstruction payante et temporisée. Une amélioration conserve le pourcentage de
coque et de bouclier restant. Les milices survivantes persistent ; seules les pertes sont
reconstituées, avec délai et coût. Les stations apparaissent avant les réserves de flottes
nombreuses, dans la limite tactique existante.

Les revenus de base des systèmes restent inchangés : les planètes ne reçoivent pas une seconde
copie de ce revenu. Seuls les bâtiments ajoutent des bonus : mine selon la richesse, commerce
+3 crédits/s/niveau, industrie +2 crédits/s/niveau et +15% de vitesse de chantier si alimentée.
Une centrale ajoute 6 unités d'énergie locale par niveau. Chaque planète dispose d'une base
énergétique de 3 ; mines, industries et installations en consomment. Un déficit local divise
par deux les bonus économiques et la vitesse des constructions planétaires. L'industrie
n'accélère alors plus le chantier naval. La barre de la vue système affiche aussi le bilan
énergétique cumulé de la faction ; l'alimentation des installations suit le bilan local.
Les stations et défenses prélèvent un entretien sur le revenu de crédits.
Les géantes gazeuses excluent les mines, l'industrie et les bâtiments militaires au sol.

La production navale conserve sa file existante : elle est accessible dans **PROD.** et livre
les unités dans une flotte permanente en orbite. Le conflit orbital suspend la campagne,
y compris les files ; après sa résolution, les files contrôlées reprennent. Une conquête
annule les commandes de l'ancien propriétaire ; les constructions planétaires attendent la
fin de l'occupation. Les IA utilisent les mêmes commandes, coûts, délais et emplacements.

Voir [les règles, les tests et les limites de cette extension](docs/ETAT_PROJET_PYTHON_0_3_DEFENSES.md).

## Batailles conservées

Les flottes commencent avec un croiseur, deux corvettes et cinq chasseurs.
Les combats utilisent leurs véritables unités, coques et boucliers. Choisir RTS ou résolution
automatique au conflit orbital. Les survivants, les pertes et la conquête persistent.
Un repli cherche un refuge voisin allié ; sans refuge, les survivants sont capturés.
Les réserves limitent le nombre d'unités tactiques actives. Les statistiques de combat restent inchangées.

## Commandes

| Entrée | Galaxie | Bataille |
|---|---|---|
| Clic gauche | Sélection de système / flotte | Sélection de vaisseau |
| Rectangle gauche | — | Sélection multiple |
| Maj + clic | — | Ajouter / retirer une unité |
| Maj + rectangle | — | Ajouter à la sélection |
| Clic droit | Itinéraire automatique vers la destination | Déplacer au sol / attaquer une cible ennemie |
| A puis clic gauche | — | Attaque-déplacement |
| S bref | — | Arrêter les unités, au relâchement |
| H | — | Tenir la position |
| Ctrl + 1–9 | — | Créer un groupe |
| 1–9 | 1–3 : vitesses ×1/×2/×4 | Rappeler un groupe |
| ZQSD / flèches | — | Caméra ; maintenir S au moins 180 ms pour descendre |
| Molette / glisser milieu | Zoom / caméra | Zoom / caméra |
| F / Tab | Centrer / parcourir les flottes | — |
| Espace | Pause galactique | Pause tactique |
| F7 | Qualité desktop / réduite | Qualité desktop / réduite |
| F8 | Activer / couper les sons | Activer / couper les sons |
| F10 | Panneau admin | Panneau admin |
| F5 / F9 | Sauvegarder / charger | Interceptés : terminer la bataille d'abord |
| Échap | Menu / reprise | Menu tactique : reprendre ou se replier |

Les boutons Ligne, Coin et Compacte appliquent une formation à la sélection.
Le clic droit sur un ennemi concentre les tirs ; les tourelles restent autonomes
pour les autres ordres. S bref et S maintenu distinguent l'arrêt de la caméra ZQSD.
Les groupes tactiques ne changent jamais la vitesse de la carte galactique.

## Sauvegardes

F5 enregistre `saves/campaign.json` depuis les sources ; F9 recharge la campagne.
Le format JSON **5** conserve la carte, les revenus, les ressources, les chantiers, les files,
les progressions, les planètes, les bâtiments, les milices, les dégâts des défenses, les sièges, les compteurs d'identifiants, les dégâts et les voyages.
Les formats 1, 2, 3 et 4 compatibles restent lisibles : économie initialisée à 600 crédits / 350 minerais
par faction, richesse déterministe pour les formats 1/2 ; les données économiques du format 3 sont conservées.
Les planètes manquantes sont générées de façon déterministe, sans station ni milice gratuite. Le chargement ne réécrit rien.
Lors du premier enregistrement d'un ancien format, son fichier est copié dans une archive
`.v1.bak`, `.v2.bak`, `.v3.bak` ou `.v4.bak` ; si elle existe, une archive numérotée est créée. Les formats inconnus
ou corrompus sont préservés et refusés. L'écriture principale est atomique.

La sauvegarde pendant un voyage ou avant un engagement est autorisée. Terminer la bataille
avant de sauvegarder les dégâts tactiques. Fermer la fenêtre ne sauvegarde pas automatiquement.
Après installation du paquet hors des sources, le dossier de sauvegarde utilise
`%LOCALAPPDATA%/StarArena/saves` ou `~/StarArena/saves`.

## Architecture et assets

- `domain` : données et génération procédurale, sans Pygame.
- `systems/planets.py` : constructions planétaires, occupation, garnisons et IA.
- `domain/planet_stats.py` : coûts, capacités et statistiques centralisés.
- `presentation/system_view.py` : vue détaillée.
- `systems/economy.py` : coûts centralisés, revenus, production, transferts et IA économique.
- `systems/simulation.py` : pas fixe, voyages et décisions militaires.
- `systems/combat.py`, `tactical.py` : batailles et application des résultats.
- `persistence.py` : validation JSON, migration et sauvegarde.
- `presentation` et `app.py` : rendu et commandes.

Les neuf PNG intégrés restent dans `assets/ships/`. Le manifeste conserve leur orientation native,
les proportions, la transparence, les caches et le secours vectoriel.
Voir [la correspondance exacte des sprites](docs/ASSETS_PNG_INTEGRES.md).
Les anciens fichiers Godot et archives sont préservés.

## Vérifications sans fenêtre

Exécuter les commandes successivement, jamais en parallèle :

```powershell
.\.venv\Scripts\python.exe -B tools\check_static.py --report
.\.venv\Scripts\python.exe -B tools\run_logic_tests.py --report
.\.venv\Scripts\python.exe -B tools\audit_ship_assets.py
```

La livraison actuelle est documentée dans [le rapport multijoueur V0.4.0](docs/MULTIPLAYER_0_4_0.md).
**198 tests réussis**, dont les 174 tests précédents et 24 contrôles multijoueurs V0.4.0.
Les tests de logique n'importent pas Pygame. La validation graphique et l'équilibrage d'une
longue campagne restent manuels ; la V0.3.0 n'est pas déclarée stable sur cette seule base.
