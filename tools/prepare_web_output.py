"""Installer les diagnostics HTML avant le chargeur WASM, sans exécuter le jeu."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import zipfile


def prepare(folder: Path):
    root=Path(__file__).resolve().parents[1]
    index=folder/'index.html'
    html=index.read_text(encoding='utf-8')
    charset='<meta charset="utf-8">'
    if charset not in html[:1024].lower():
        position=html.lower().find('<html')
        position=html.find('>',position)+1
        if position<=0: raise ValueError('Élément html absent du build.')
        html=html[:position]+charset+'\n'+html[position:]
    # Ce préchargement du template 0.9 pointe vers une ressource inexistante.
    html=html.replace('/pythonrc.py','/cpythonrc.py')
    marker='<script src="./star-arena-boot.js"></script>'
    if marker not in html:
        position=html.find('<script ')
        if position<0: raise ValueError('Chargeur Pygbag absent du HTML.')
        html=html[:position]+marker+'\n'+html[position:]
    index.write_text(html,encoding='utf-8')
    (folder/'star-arena-boot.js').write_bytes((root/'web/boot.js').read_bytes())
    try:
        git_result=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True,check=False)
        revision=git_result.stdout.strip() if git_result.returncode==0 else None
    except FileNotFoundError:
        revision=None
    archives=list(folder.glob('*.apk'))
    archive=archives[0] if len(archives)==1 else None
    art_digest=None
    if archive:
        with zipfile.ZipFile(archive) as package:
            art_digest=hashlib.sha256(package.read('assets/star_arena/presentation/art.py')).hexdigest()
    report={'index_sha256':hashlib.sha256(index.read_bytes()).hexdigest(),
            'boot_script_before_runtime':html.index(marker)<html.index('pythons.js'),
            'source_commit':revision,
            'package_sha256':hashlib.sha256(archive.read_bytes()).hexdigest() if archive else None,
            'art_sha256':art_digest,
            'browser_tested':False}
    (folder/'build-info.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    print(json.dumps(prepare(parser.parse_args().folder),indent=2))
