"""Audit léger de l'index Git avant publication ; ne montre jamais les valeurs suspectes."""
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = {'.venv', '.venv-web', '__pycache__', 'saves', 'settings',
                   'web_build', 'build', 'dist', 'outputs', 'work', '.codex', '.agents',
                   '.pytest_cache', '.ruff_cache', '.mypy_cache'}
ALLOWED_ROOT_FILES = {'.gitignore', 'AGENTS.md', 'README.md', 'main.py', 'pyproject.toml',
                      'requirements.txt', 'requirements-web.txt'}
ALLOWED_FOLDERS = {'src', 'assets', 'docs', 'web', 'tools', 'tests', '.github', '.vscode'}
SUSPICIOUS = {
    'clé privée': re.compile(r'-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----'),
    'jeton GitHub': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b'),
    'clé AWS': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'chemin de profil personnel': re.compile(r'[A-Za-z]:[/\\]+Users[/\\]+[^\s/\\"<>]+|/(?:Users|home)/[^\s/"<>]+'),
    'secret littéral': re.compile(r'''(?i)(?:api[_-]?key|password|access[_-]?token|client[_-]?secret)\s*[=:]\s*["'][A-Za-z0-9_+/=.-]{16,}["']'''),
}


def audit():
    raw = subprocess.check_output(['git', 'ls-files', '--stage', '-z'], cwd=ROOT)
    files = []; findings = []; total = 0
    for item in raw.split(b'\0'):
        if not item:
            continue
        metadata, name = item.split(b'\t', 1)
        mode, oid, stage = metadata.decode('ascii').split()
        path = name.decode('utf-8')
        parts = path.split('/')
        files.append(path)
        if (mode != '100644' or stage != '0' or any(p in FORBIDDEN_PARTS for p in parts)
                or any(p.startswith(('STAR_ARENA_GALACTIC_CONQUEST', 'arena-net-', 'Untitled-')) for p in parts)
                or (len(parts) == 1 and path not in ALLOWED_ROOT_FILES)
                or (len(parts) > 1 and parts[0] not in ALLOWED_FOLDERS)
                or Path(path).suffix.lower() in {'.pyc','.tmp','.log','.bak','.pem','.key','.pfx','.p12','.zip','.7z','.rar'}
                or Path(path).name.startswith('.env')):
            findings.append({'file': path, 'reason': 'chemin ou mode Git non autorisé'})
            continue
        content = subprocess.check_output(['git', 'cat-file', 'blob', oid], cwd=ROOT)
        total += len(content)
        if Path(path).suffix.lower() in ('.png', '.wav', '.ogg'):
            continue
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            findings.append({'file': path, 'reason': 'fichier binaire inattendu'})
            continue
        # Le code du scanner contient nécessairement ses propres expressions de détection.
        if path == 'tools/audit_publication.py':
            continue
        for label, pattern in SUSPICIOUS.items():
            for match in pattern.finditer(text):
                findings.append({'file': path, 'line': text.count('\n',0,match.start())+1, 'reason': label})
    required = {'.github/workflows/pages.yml','web/browser.js','web/README.md','web/.nojekyll',
                'src/star_arena/app.py','src/star_arena/network/runtime.py','src/star_arena/web.py',
                'tools/prepare_web.py','tools/check_web_build.py','README.md','main.py'}
    if not required.issubset(files):
        findings.append({'reason': 'fichiers requis manquants', 'files': sorted(required-set(files))})
    pngs = [p for p in files if p.startswith('assets/ships/') and p.endswith('.png')]
    music = [p for p in files if p.startswith('assets/audio/music/') and p.endswith(('.wav','.ogg'))]
    if len(pngs) != 9 or len(music) != 6:
        findings.append({'reason': 'inventaire des assets inattendu'})
    return {'scope': 'Index Git exact, avant commit/publication', 'files': files, 'count': len(files),
            'bytes': total, 'ship_pngs': len(pngs), 'music_files': len(music), 'findings': findings,
            'success': not findings, 'limitation': 'Détection de motifs, pas une garantie absolue d’absence de secrets.'}


if __name__ == '__main__':
    result = audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['success'] else 1)
