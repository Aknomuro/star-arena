/* Chargé AVANT le runtime : reste visible même si Python ne démarre jamais. */
(() => {
    'use strict';
    if (window.starArenaBoot) return;
    const originalError = console.error.bind(console);
    let panel, title, detail;
    const boot = window.starArenaBoot = {
        state:'loading', phase:'runtime',
        message:'Chargement de Python/WASM… Cliquez dans le jeu si le chargeur le demande.',
        history:[],
        step(phase, message) {
            this.phase = String(phase);
            this.message = String(message).slice(-12000);
            this.history.push({phase:this.phase,message:this.message});
            if (this.history.length > 30) this.history.shift();
            this.state = phase === 'menu' ? 'ready' : phase === 'error' ? 'error' : 'loading';
            if (phase === 'error') originalError('[STAR ARENA boot]',this.message);
            else console.info('[STAR ARENA boot]',phase,this.message);
            paint();
        }
    };
    function paint() {
        if (!panel) return;
        panel.hidden = boot.state === 'ready';
        title.textContent = boot.state === 'error' ? 'STAR ARENA — erreur de démarrage' : 'STAR ARENA — chargement';
        detail.textContent = boot.message;
        panel.style.borderColor = boot.state === 'error' ? '#f18181' : '#4daeca';
    }
    function mount() {
        panel = document.createElement('section');
        panel.id = 'star-arena-boot'; panel.setAttribute('role','status');
        panel.style.cssText = 'position:fixed;z-index:1000;top:12px;left:12px;right:12px;max-width:850px;margin:auto;padding:16px;background:#0f1a29f2;color:#e0edf4;border:1px solid #4daeca;border-radius:8px;font:15px sans-serif;pointer-events:none';
        title = document.createElement('strong');
        detail = document.createElement('pre');
        detail.style.cssText = 'white-space:pre-wrap;overflow-wrap:anywhere;max-height:45vh;overflow:auto;font:13px monospace;pointer-events:auto';
        panel.append(title,detail); document.body.append(panel); paint();
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',mount,{once:true});
    else mount();
    window.addEventListener('error',event => {
        if (event.error || event.message) boot.step('error',event.error?.stack || event.message);
        else if (event.target?.tagName === 'SCRIPT') boot.step('error','Script impossible à charger : '+event.target.src);
    },true);
    window.addEventListener('unhandledrejection',event => boot.step('error',event.reason?.stack || String(event.reason)));
    // Certains ponts WASM signalent les exceptions Python uniquement dans stderr.
    console.error = (...args) => {
        originalError(...args);
        const message = args.map(String).join(' ');
        if (/Traceback|ModuleNotFoundError|ImportError|SyntaxError|RuntimeError|Aborted\(/.test(message)) boot.step('error',message);
    };
    setTimeout(() => {
        if (boot.state === 'loading') {
            boot.message = 'Démarrage toujours en attente ('+boot.phase+'). Cliquez dans le canvas, puis consultez F12 → Console si le menu reste absent. Vérifiez les téléchargements du CDN Pygbag.';
            paint(); console.warn('[STAR ARENA boot]',boot.message);
        }
    },60000);
})();
