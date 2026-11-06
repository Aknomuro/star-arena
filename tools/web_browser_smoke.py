"""Test Chromium réservé au runner GitHub Actions : jamais lancé automatiquement sur le PC."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from threading import Thread


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('Ce test graphique est réservé au runner GitHub Actions.')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    parser.add_argument('--url')
    parser.add_argument('--diagnostic-only',action='store_true')
    args=parser.parse_args()
    from playwright.sync_api import sync_playwright
    output=Path('browser-smoke'); output.mkdir(exist_ok=True)
    logs=[]; result={'menu_visible':False,'browser':'Chromium headless GitHub Actions'}
    # Reproduire aussi un hébergement sous /star-arena/, pas seulement à la racine.
    class Handler(SimpleHTTPRequestHandler):
        def translate_path(self,path):
            if path.startswith('/star-arena/'):
                path=path[len('/star-arena'):]
            return super().translate_path(path)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(args.folder.resolve())))
    thread=Thread(target=server.serve_forever,daemon=True); thread.start()
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True,args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
            page=browser.new_page(viewport={'width':1440,'height':1000})
            page.on('console',lambda msg:logs.append({'type':msg.type,'text':msg.text}))
            page.on('pageerror',lambda error:logs.append({'type':'pageerror','text':str(error)}))
            page.on('response',lambda response:logs.append({'type':'http-error','status':response.status,'url':response.url}) if response.status>=400 else None)
            result['url']=args.url or f'http://127.0.0.1:{server.server_port}/star-arena/'
            try:
                page.goto(result['url'],wait_until='domcontentloaded',timeout=60000)
                for _ in range(90):
                    state=page.evaluate('window.starArenaBoot ? {state:starArenaBoot.state,phase:starArenaBoot.phase,message:starArenaBoot.message,history:starArenaBoot.history} : null')
                    if state and state['state'] in ('ready','error'):
                        result['boot']=state
                        break
                    page.locator('#canvas').click(position={'x':640,'y':400},timeout=1000,force=True) if page.locator('#canvas').count() else None
                    page.wait_for_timeout(2000)
                result['boot']=page.evaluate('window.starArenaBoot ? {state:starArenaBoot.state,phase:starArenaBoot.phase,message:starArenaBoot.message,history:starArenaBoot.history} : null')
                result['canvas']=page.locator('#canvas').evaluate('(c)=>({width:c.width,height:c.height,visible:c.getBoundingClientRect().width>0})')
                result['menu_visible']=bool(result['boot'] and result['boot']['state']=='ready' and result['canvas']['visible'])
                page.screenshot(path=str(output/'menu.png'))
            except Exception as error:
                result['error']=str(error)
            finally:
                browser.close()
    finally:
        server.shutdown(); server.server_close(); thread.join()
        (output/'console.json').write_text(json.dumps(logs,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['menu_visible'] or args.diagnostic_only else 1


if __name__=='__main__': raise SystemExit(main())
