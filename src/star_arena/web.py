"""Adaptateur navigateur injecté ; aucun import graphique, réseau ou JS au chargement."""
from dataclasses import asdict
import json
from pathlib import Path

from star_arena.config import MAX_SAVE_BYTES, project_root
from star_arena.persistence import campaign_payload, decode, _unique_keys, _invalid_constant
from star_arena.presentation.audio_settings import AudioSettings, decode_settings


def decode_text(raw: str):
    if not isinstance(raw, str) or len(raw.encode('utf-8')) > MAX_SAVE_BYTES:
        raise ValueError('Sauvegarde trop volumineuse (maximum 2 Mo).')
    return decode(json.loads(raw, object_pairs_hook=_unique_keys, parse_constant=_invalid_constant))


def encode_campaign(campaign):
    raw = json.dumps(campaign_payload(campaign), ensure_ascii=False, allow_nan=False,
                     separators=(',', ':'))
    decode_text(raw)
    return raw


class BrowserStore:
    """Même validation de campagne que sur PC ; écriture atomique avec conflit d'onglet détecté."""
    def __init__(self, bridge):
        self.bridge = bridge
        self.expected = {}

    def read(self, key):
        value = self.bridge.call('read', key)
        self.expected[key] = value
        return value

    def write(self, key, value):
        if key not in self.expected:
            self.read(key)
        self.bridge.call('write', key, value, self.expected[key])
        self.expected[key] = value

    def load(self):
        raw = self.read('campaign')
        if raw is None:
            raise ValueError('Aucune campagne enregistrée dans ce navigateur.')
        return decode_text(raw)

    def save(self, campaign):
        raw = encode_campaign(campaign)
        if 'campaign' not in self.expected:
            self.read('campaign')
        previous = self.expected['campaign']
        if previous is not None:
            decode_text(previous)  # Conserver une sauvegarde inconnue ou corrompue.
        self.write('campaign', raw)

    def load_preferences(self):
        raw = self.read('audio')
        if raw is None:
            return AudioSettings()
        if len(raw.encode('utf-8')) > 8192:
            raise ValueError('Préférences audio trop volumineuses.')
        return decode_settings(json.loads(raw))

    def save_preferences(self, settings):
        value = {'version': 1, 'audio': asdict(settings)}
        decode_settings(value)
        if 'audio' not in self.expected:
            self.read('audio')
        if self.expected['audio'] is not None:
            decode_settings(json.loads(self.expected['audio']))
        self.write('audio', json.dumps(value, allow_nan=False))


class BrowserBridge:
    def __init__(self, window):
        script = project_root() / 'web' / 'browser.js'
        window.eval(script.read_text(encoding='utf-8'))
        self.api = window.starArenaWeb

    def call(self, operation, *args):
        result = json.loads(str(self.api.call(operation, json.dumps(args, ensure_ascii=True))))
        if not result.get('ok'):
            raise ValueError(result.get('error', 'Service navigateur indisponible.'))
        return result.get('value')


class WebMultiplayer:
    """Point d'extension d'un futur transport Web ; aucune socket Python sur navigateur."""
    active = False
    is_host = False
    client = server = task = state = None
    status = 'Multijoueur Web en préparation'

    def poll(self):
        pass

    async def close(self):
        pass


def poll_browser(app):
    """Au plus une intention DOM par frame, sans boucle d'attente."""
    if app.browser is None:
        return
    try:
        event = app.browser.call('poll')
        if event:
            action = event.get('action')
            if action == 'audio_unlock':
                app.needs_audio_unlock = False
                app.configure_audio(persist=False)
            elif action == 'error':
                app.message = event.get('message', 'Erreur navigateur.')[:240]
            elif action == 'import':
                if app.mode == 'battle' or (app.simulation and app.simulation.campaign.pending):
                    raise ValueError('Terminer la bataille avant de remplacer la campagne. Import non appliqué.')
                campaign = decode_text(event.get('text'))
                app.begin(campaign)
                app.message = 'JSON importé en mémoire. Cliquez Sauver pour le conserver dans ce navigateur.'
            elif action in ('save', 'load', 'web_export', 'web_admin', 'audio_settings', 'quality_toggle'):
                app.action(action)
        audio_error = app.audio.error or next(iter(app.music.errors.values()), '')
        app.browser.call('status', app.message + (' · Audio indisponible : ' + audio_error if audio_error else ''))
    except (ValueError, OSError, TypeError, RecursionError) as error:
        app.message = 'Navigateur : ' + str(error)
