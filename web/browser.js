/* Pont Pygbag : stockage par chemin Pages, DOM et téléchargements sans serveur. */
(() => {
    'use strict';
    if (window.starArenaWeb) return;
    const events = [];
    const base = new URL('.', window.location.href).pathname;
    const prefix = 'star-arena:v1:' + base + ':';
    let picked = false;
    const push = event => {
        if (events.length < 8) events.push(event);
        else status.textContent = 'Commande non envoyée : trop de demandes en attente.';
    };
    const bar = document.createElement('div');
    bar.id = 'star-arena-controls';
    bar.style.cssText = 'background:#0f1a29;color:#dbe6f0;padding:8px;font:14px sans-serif;position:relative;z-index:10';
    bar.setAttribute('aria-label', 'Commandes STAR ARENA');
    const status = document.createElement('div');
    status.setAttribute('role', 'status');
    status.style.cssText = 'padding-top:6px;white-space:normal';
    status.textContent = 'Solo Web · Cliquez dans le jeu pour activer le son. Sauvegarde locale à ce navigateur.';
    function button(label, fn) {
        const b = document.createElement('button');
        b.textContent = label;
        b.style.cssText = 'margin:2px;padding:7px 10px;cursor:pointer';
        b.addEventListener('click', fn);
        bar.appendChild(b);
    }
    for (const [label, action] of [['Sauver','save'],['Charger','load'],['Exporter JSON','web_export'],
        ['Audio','audio_settings'],['Qualité','quality_toggle'],['Admin solo','web_admin']]) {
        button(label, () => push({action}));
    }
    const picker = document.createElement('input');
    picker.type = 'file'; picker.accept = '.json,application/json'; picker.hidden = true;
    picker.addEventListener('change', async () => {
        const file = picker.files[0];
        if (!file || picked) return;
        picked = true;
        try {
            if (file.size > 2000000) throw Error('JSON trop volumineux (maximum 2 Mo).');
            const text = await file.text();
            push({action:'import', text});
        } catch (e) { push({action:'error', message:String(e.message || e)}); }
        finally { picker.value = ''; picked = false; }
    });
    button('Importer JSON', () => picker.click());
    button('Plein écran', () => {
        const request = document.documentElement.requestFullscreen;
        if (!request) { push({action:'error', message:'Plein écran indisponible.'}); return; }
        if (document.fullscreenElement) document.exitFullscreen().catch(e => push({action:'error',message:String(e)}));
        else request.call(document.documentElement).catch(e => push({action:'error', message:String(e)}));
    });
    bar.append(picker, status);
    document.body.prepend(bar);
    const style = document.createElement('style');
    style.textContent = 'html,body{margin:0;background:#090f1a}canvas.emscripten,canvas{position:relative!important;inset:auto!important;border:0!important;padding:0!important;max-width:100%;object-fit:contain;touch-action:none;display:block;margin:auto!important}';
    document.head.append(style);
    function fit() {
        const canvas = document.querySelector('canvas');
        if (!canvas) return;
        const height = Math.max(120, window.innerHeight - bar.offsetHeight - 8);
        const width = Math.min(window.innerWidth, height * 1.6);
        canvas.style.width = width + 'px';
        canvas.style.height = (width / 1.6) + 'px';
        canvas.tabIndex = 0;
    }
    fit(); window.addEventListener('resize', fit);
    new ResizeObserver(fit).observe(bar);
    // Le canvas peut être créé après le pont. Aucune boucle de polling DOM.
    new MutationObserver(fit).observe(document.body, {childList:true});
    document.addEventListener('wheel', e => {
        if (e.target.tagName === 'CANVAS') e.preventDefault();
    }, {passive:false});
    document.addEventListener('contextmenu', e => {
        if (e.target.tagName === 'CANVAS') e.preventDefault();
    });
    document.addEventListener('pointerdown', e => {
        if (e.target.tagName === 'CANVAS') e.target.focus({preventScroll:true});
    });
    document.addEventListener('keydown', e => {
        if (document.activeElement?.tagName === 'CANVAS' &&
            ['Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Tab','F5','F7','F8','F9','F10'].includes(e.code)) e.preventDefault();
    });
    let unlocked = false;
    function unlock() {
        if (unlocked) return;
        unlocked = true;
        const context = window.SDL2?.audioContext;
        if (context?.state === 'suspended') context.resume().catch(() => {});
        push({action:'audio_unlock'});
    }
    document.addEventListener('pointerdown', unlock, {capture:true});
    document.addEventListener('keydown', unlock, {capture:true});
    window.addEventListener('beforeunload', e => {
        // Une sauvegarde explicite reste nécessaire ; ne pas promettre d'autosave.
        e.preventDefault(); e.returnValue = '';
    });
    window.starArenaWeb = {
        call(operation, encoded) {
            try {
                const args = JSON.parse(encoded);
                let value = null;
                if (operation === 'read') value = window.localStorage.getItem(prefix + args[0]);
                else if (operation === 'write') {
                    const key = prefix + args[0];
                    if (window.localStorage.getItem(key) !== args[2])
                        throw Error('Sauvegarde modifiée dans un autre onglet. Exportez la campagne courante avant de recharger.');
                    window.localStorage.setItem(key, args[1]);
                } else if (operation === 'poll') value = events.shift() || null;
                else if (operation === 'status') status.textContent = args[0];
                else if (operation === 'download') {
                    const url = URL.createObjectURL(new Blob([args[0]], {type:'application/json;charset=utf-8'}));
                    const link = document.createElement('a');
                    link.href = url; link.download = 'star-arena-campaign.json';
                    document.body.append(link); link.click(); link.remove();
                    setTimeout(() => URL.revokeObjectURL(url), 10000);
                } else throw Error('Opération navigateur inconnue.');
                return JSON.stringify({ok:true, value});
            } catch (e) {
                return JSON.stringify({ok:false, error:'Stockage/service indisponible : ' + String(e.message || e) + '. Exportez votre campagne pour la conserver.'});
            }
        }
    };
})();
