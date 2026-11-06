"""Valider l'artefact Pygbag sans exécuter de navigateur ; aucun export implicite."""
import argparse
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import zipfile
import sys
import hashlib
import json


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths=[]

    def handle_starttag(self, tag, attrs):
        for key,value in attrs:
            if key in ('src','href') and value:
                self.paths.append(value)


def check(folder: Path, *, require_startup=False):
    if not (folder/'index.html').is_file():
        raise ValueError('index.html absent : un staging Python ne constitue pas un build Web.')
    html=(folder/'index.html').read_text(encoding='utf-8')
    if require_startup:
        marker='<script src="./star-arena-boot.js"></script>'
        if marker not in html or html.index(marker)>html.index('pythons.js'):
            raise ValueError('Diagnostic de démarrage absent ou chargé après le runtime.')
        if (folder/'star-arena-boot.js').read_bytes() != (Path(__file__).resolve().parents[1]/'web/boot.js').read_bytes():
            raise ValueError('Script de diagnostic absent ou différent.')
    refs=References(); refs.feed(html)
    if any(path.startswith('/') and not path.startswith('//') for path in refs.paths):
        raise ValueError('Référence absolue à la racine incompatible avec /star-arena/.')
    archives=list(folder.glob('*.apk'))
    if len(archives)!=1:
        raise ValueError('Une archive de jeu Pygbag .apk est requise (archive ZIP, pas application Android).')
    root=Path(__file__).resolve().parents[1]
    if require_startup:
        info=json.loads((folder/'build-info.json').read_text(encoding='utf-8'))
        if info.get('package_sha256')!=hashlib.sha256(archives[0].read_bytes()).hexdigest():
            raise ValueError('Provenance du paquet périmée : régénérer le build depuis les sources.')
        with zipfile.ZipFile(archives[0]) as package:
            digest=hashlib.sha256(package.read('assets/star_arena/presentation/art.py')).hexdigest()
        if info.get('art_sha256')!=digest:
            raise ValueError('Empreinte de art.py différente du paquet publié.')
    # Comparaison exacte avec la liste autorisée, pas seulement une liste noire.
    from prepare_web import files_for_web, web_bytes, web_path
    sources={web_path(root,p).as_posix():p for p in files_for_web(root)}
    allowed=set(sources)
    with zipfile.ZipFile(archives[0]) as archive:
        seen=set()
        for info in archive.infolist():
            if info.is_dir(): continue
            name=PurePosixPath(info.filename)
            if not name.parts or name.parts[0]!='assets':
                raise ValueError('Racine inattendue dans le paquet : '+info.filename)
            relative=PurePosixPath(*name.parts[1:]).as_posix()
            if relative not in allowed or relative in seen:
                raise ValueError('Fichier inattendu ou dupliqué : '+relative)
            seen.add(relative)
            if archive.read(info)!= web_bytes(root,sources[relative]):
                raise ValueError('Contenu inattendu : '+relative)
            if relative.endswith('.py'):
                compile(archive.read(info),relative,'exec')
        if seen!=allowed:
            raise ValueError('Fichiers manquants dans le paquet : '+', '.join(sorted(allowed-seen)))
    (folder/'.nojekyll').touch()
    return len(seen)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    parser.add_argument('--startup',action='store_true')
    args=parser.parse_args()
    try:
        print('Paquet vérifié :',check(args.folder,require_startup=args.startup),'fichiers. Navigateur NON TESTÉ.')
    except (ValueError,OSError,SyntaxError,zipfile.BadZipFile) as error:
        print(str(error),file=sys.stderr); return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
