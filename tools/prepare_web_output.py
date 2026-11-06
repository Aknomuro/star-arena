"""Installer les diagnostics HTML avant le chargeur WASM, sans exécuter le jeu."""
from pathlib import Path
import argparse
import hashlib
import json


def prepare(folder: Path):
    root=Path(__file__).resolve().parents[1]
    index=folder/'index.html'
    html=index.read_text(encoding='utf-8')
    marker='<script src="./star-arena-boot.js"></script>'
    if marker not in html:
        position=html.find('<script ')
        if position<0: raise ValueError('Chargeur Pygbag absent du HTML.')
        html=html[:position]+marker+'\n'+html[position:]
        index.write_text(html,encoding='utf-8')
    (folder/'star-arena-boot.js').write_bytes((root/'web/boot.js').read_bytes())
    report={'index_sha256':hashlib.sha256(index.read_bytes()).hexdigest(),
            'boot_script_before_runtime':html.index(marker)<html.index('pythons.js'),
            'browser_tested':False}
    (folder/'build-info.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    print(json.dumps(prepare(parser.parse_args().folder),indent=2))
