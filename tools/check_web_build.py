"""Valider l'artefact Pygbag sans exécuter de navigateur ; aucun export implicite."""
import argparse
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import zipfile
import sys


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths=[]

    def handle_starttag(self, tag, attrs):
        for key,value in attrs:
            if key in ('src','href') and value:
                self.paths.append(value)


def check(folder: Path):
    if not (folder/'index.html').is_file():
        raise ValueError('index.html absent : un staging Python ne constitue pas un build Web.')
    html=(folder/'index.html').read_text(encoding='utf-8')
    refs=References(); refs.feed(html)
    if any(path.startswith('/') and not path.startswith('//') for path in refs.paths):
        raise ValueError('Référence absolue à la racine incompatible avec /star-arena/.')
    archives=list(folder.glob('*.apk'))
    if len(archives)!=1:
        raise ValueError('Une archive de jeu Pygbag .apk est requise (archive ZIP, pas application Android).')
    root=Path(__file__).resolve().parents[1]
    # Comparaison exacte avec la liste autorisée, pas seulement une liste noire.
    from prepare_web import files_for_web, web_bytes
    allowed={p.relative_to(root).as_posix() for p in files_for_web(root)}
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
            if archive.read(info)!= web_bytes(root,root/relative):
                raise ValueError('Contenu inattendu : '+relative)
        if seen!=allowed:
            raise ValueError('Fichiers manquants dans le paquet : '+', '.join(sorted(allowed-seen)))
    (folder/'.nojekyll').touch()
    return len(seen)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    args=parser.parse_args()
    try:
        print('Paquet vérifié :',check(args.folder),'fichiers. Navigateur NON TESTÉ.')
    except (ValueError,OSError,zipfile.BadZipFile) as error:
        print(str(error),file=sys.stderr); return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
