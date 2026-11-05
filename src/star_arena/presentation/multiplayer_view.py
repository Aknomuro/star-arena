"""Menus LAN : rendu seul ; les sockets et la campagne restent dans network."""
from star_arena.domain.models import FACTIONS


def draw_multiplayer(ui,app):
    mp=app.mp; state=mp.state
    ui.panel((190,70,900,650))
    ui.text('MULTIJOUEUR PC / LAN',225,93,38)
    ui.text('Hôte autoritaire · 2–3 joueurs · aucune ouverture automatique de routeur',225,149,16)
    if app.mode=='mp_menu':
        ui.button('mp_create_form','Créer une partie',(225,220,830,46))
        ui.button('mp_join_form','Rejoindre / reconnecter',(225,280,830,46))
        ui.button('mp_load_host','Héberger la sauvegarde multijoueur',(225,340,830,46))
        ui.button('mp_solo','Retour au mode solo',(225,410,830,46))
        ui.wrapped('Pour charger une session, garder le même port ou indiquer le nouveau aux invités. Les clés personnelles permettent de retrouver les places sauvegardées.',225,490,800,3)
    elif app.mode in ('mp_create_form','mp_join_form'):
        create=app.mode=='mp_create_form'
        fields=(('name','Votre nom'),('party','Nom de partie'),('bind','Écoute LAN (0.0.0.0)'),('port','Port'),('seed','Graine de galaxie')) if create else (
            ('name','Votre nom'),('address','IP locale de l’hôte'),('port','Port'),('invite','Invitation commune'),('reconnect','Clé personnelle (optionnelle)'))
        for i,(key,label) in enumerate(fields):
            y=202+i*55
            ui.text(label,225,y+8,16)
            value=mp.fields[key]
            if key=='reconnect' and value and mp.focus!=key: value='•'*min(20,len(value))
            ui.button('mp_field:'+key,value or 'Cliquer puis saisir / Ctrl+V',(520,y,535,43),active=mp.focus==key)
        ui.button('mp_host' if create else 'mp_join','Ouvrir le salon' if create else 'Rejoindre / reconnecter',(225,514,830,42))
        if not create:
            ui.button('mp_join_fresh','Nouvelle place (ignorer la clé mémorisée)',(225,562,830,36))
        ui.button('mp_menu','Retour',(225,611,830,36))
    elif app.mode=='mp_lobby' and state:
        ui.text(state['name']+f" · {len(state['participants'])}/3 joueurs",225,195,24,width=820)
        if mp.server:
            ui.text(f"Port LAN : {mp.server.port} · utiliser l’IP de ce PC sur le réseau",225,233,16)
            ui.text('Invitation : '+mp.server.authority.invite,225,260,16,width=650)
            ui.button('mp_copy_invite','Copier',(945,254,110,29))
        else:
            ui.text('Connecté à '+mp.fields['address']+':'+mp.fields['port'],225,233,16)
        for i,p in enumerate(state['participants']):
            y=303+i*44
            ui.text(p['name']+' · '+FACTIONS[p['faction']].name+' · '+('connecté' if p['online'] else 'absent — place réservée'),225,y,16,width=680)
            if mp.is_host and not p['online']:
                ui.button('mp_reinvite:'+p['id'],'Réinviter',(934,y-2,120,31))
        for i,f in enumerate(FACTIONS):
            ui.button('mp_faction:'+str(i),f.name,(225+i*281,447,270,36),not state['started'])
        ui.text(f"Galaxie : {state['size']} · graine {state['seed']}",225,499,14,width=260)
        for i,size in enumerate((15,30,60,100)):
            ui.button('mp_size:'+str(size),str(size),(495+i*90,491,80,34),mp.is_host and not state['started'] and state['campaign'] is None)
        ui.button('mp_start','Démarrer / reprendre — hôte',(225,543,830,40),mp.is_host and not state['started'])
        ui.button('mp_leave','Quitter la session',(225,593,830,36))
        if mp.private_invite:
            ui.text('Clé personnelle : '+mp.private_invite,225,637,14,width=690)
            ui.button('mp_copy_personal','Copier',(945,634,110,27))
    else:
        ui.text('Connexion et synchronisation en cours…',225,230,18)
        ui.button('mp_leave','Annuler / quitter',(225,315,830,42))
    ui.wrapped(mp.profile_error or mp.status,225,679,830,1)


def draw_session_menu(ui,app):
    ui.panel((245,130,790,550))
    ui.text('SESSION MULTIJOUEUR',280,158,38)
    ui.text('La simulation continue sur l’hôte ; les menus sont locaux.',280,220,16)
    ui.button('resume','Revenir à la campagne',(280,270,720,42))
    ui.button('save','Sauvegarder sur l’hôte',(280,326,720,42),app.mp.is_host)
    ui.button('mp_save_leave','Sauvegarder puis fermer la session',(280,382,720,42),app.mp.is_host)
    ui.button('mp_leave','Quitter sans sauvegarde automatique',(280,438,720,42))
    ui.button('audio_settings','Paramètres audio',(280,494,720,42))
    ui.wrapped(app.mp.status,280,561,720,3)
