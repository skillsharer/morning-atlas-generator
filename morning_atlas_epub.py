#!/usr/bin/env python3
"""Kindle EPUB from Morning Atlas JSON. Python standard library only.
Usage: python morning_atlas_epub.py example_edition.json --out-dir output --verify
"""
import argparse, html, json, re, uuid, zipfile
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

def esc(x): return html.escape(str(x), quote=True)
def rich(x):
    x=esc(x)
    x=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',x)
    return re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)',r'<em>\1</em>',x)
def page(title,content):
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
      '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en"><head>'
      '<meta charset="utf-8"/><title>'+esc(title)+'</title>'
      '<link rel="stylesheet" href="style.css" type="text/css"/></head><body>'+content+'</body></html>')
CSS='''body{font-family:serif;line-height:1.5;margin:.4em}h1,h2{line-height:1.2}h1{font-size:1.6em}.masthead{text-align:center;font-size:2.2em;letter-spacing:.03em}.issue,.section{font-family:sans-serif;font-size:.8em;letter-spacing:.08em}.issue,.tagline{text-align:center}.tagline,.deck{font-style:italic}.section{text-transform:uppercase;margin-top:1em}.article{page-break-before:always}p{margin-bottom:1em;orphans:2;widows:2}.sources{font-size:.85em;margin-top:1.5em}a{color:inherit}'''
def validate(d):
    date.fromisoformat(d['date'])
    if not d.get('articles'): raise ValueError('No articles')
    for a in d['articles']:
        if not a.get('section') or not a.get('headline') or not isinstance(a.get('paragraphs'),list): raise ValueError('Bad article')
        for s in a.get('sources',[]):
            u=urlparse(s['url'])
            if u.scheme not in ('https','http') or not u.netloc: raise ValueError('Invalid source URL')
def build(d,out):
    validate(d)
    chapters=[]
    for i,a in enumerate(d['articles'],1):
        body='<section class="article"><p class="section">'+esc(a['section'])+'</p><h1>'+esc(a['headline'])+'</h1>'
        if a.get('deck'): body+='<p class="deck">'+rich(a['deck'])+'</p>'
        body+=''.join('<p>'+rich(p)+'</p>' for p in a['paragraphs'])
        if a.get('sources'):
            body+='<div class="sources"><h2>Sources</h2><ul>'
            body+=''.join('<li><a href="'+esc(s['url'])+'">'+esc(s.get('label',s['url']))+'</a></li>' for s in a['sources'])+'</ul></div>'
        chapters.append((f'article-{i:03}.xhtml',a['headline'],page(a['headline'],body+'</section>')))
    if d.get('closing_note'):
        chapters.append(('closing.xhtml',"Editor's closing note",page("Editor's closing note",'<section class="article"><h1>Editor’s closing note</h1><p>'+rich(d['closing_note'])+'</p></section>')))
    cover=page('The Morning Atlas','<h1 class="masthead">THE MORNING ATLAS</h1><p class="issue">'+esc(d['date'])+' · '+esc(d.get('edition','Daily edition'))+'</p><p class="tagline">'+esc(d.get('tagline',''))+'</p><p><a href="nav.xhtml">Contents</a></p>')
    nav=page('Contents','<nav xmlns:epub="http://www.idpf.org/2007/ops" epub:type="toc"><h1>Contents</h1><ol>'+''.join('<li><a href="'+f+'">'+esc(t)+'</a></li>' for f,t,_ in chapters)+'</ol></nav>')
    manifest=['<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>','<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>','<item id="css" href="style.css" media-type="text/css"/>']
    spine=['<itemref idref="cover"/>','<itemref idref="nav"/>']
    for i,(f,_,_) in enumerate(chapters,1):
        manifest.append(f'<item id="ch{i}" href="{f}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="ch{i}"/>')
    uid=uuid.uuid5(uuid.NAMESPACE_URL,'morning-atlas:'+d['date'])
    opf=('<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id" xml:lang="en">'
         '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">urn:uuid:'+str(uid)+'</dc:identifier><dc:title>The Morning Atlas — '+esc(d['date'])+'</dc:title><dc:language>en</dc:language><dc:creator>The Morning Atlas</dc:creator><meta property="dcterms:modified">'+esc(d['date'])+'T07:00:00Z</meta></metadata><manifest>'+''.join(manifest)+'</manifest><spine>'+''.join(spine)+'</spine></package>')
    container='<?xml version="1.0" encoding="UTF-8"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'
    out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('mimetype','application/epub+zip',compress_type=zipfile.ZIP_STORED)
        for f,v in [('META-INF/container.xml',container),('OEBPS/content.opf',opf),('OEBPS/style.css',CSS),('OEBPS/cover.xhtml',cover),('OEBPS/nav.xhtml',nav)]:z.writestr(f,v)
        for f,_,v in chapters:z.writestr('OEBPS/'+f,v)
def verify(out,d):
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None and z.namelist()[0]=='mimetype' and z.read('mimetype')==b'application/epub+zip'
        for f in ('META-INF/container.xml','OEBPS/content.opf','OEBPS/cover.xhtml','OEBPS/nav.xhtml'): ET.fromstring(z.read(f))
        for i,a in enumerate(d['articles'],1):
            raw=z.read(f'OEBPS/article-{i:03}.xhtml').decode()
            ET.fromstring(raw)
            for text in [esc(a['headline']),esc(a['section'])]+[rich(p) for p in a['paragraphs']]+[esc(s['url']) for s in a.get('sources',[])]:
                if text not in raw:raise ValueError(f'Missing content in article {i}: {text[:50]}')
        if d.get('closing_note') and rich(d['closing_note']) not in z.read('OEBPS/closing.xhtml').decode():raise ValueError('Missing closing note')
    return len(d['articles'])
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('manuscript',type=Path);p.add_argument('--out-dir',type=Path,default=Path('output'));p.add_argument('--verify',action='store_true')
    a=p.parse_args();d=json.loads(a.manuscript.read_text(encoding='utf-8'))
    dest=a.out_dir/f'Morning_Atlas_{d["date"]}.epub';build(d,dest)
    if a.verify:print(f'Verified {verify(dest,d)} complete articles and EPUB structure')
    print('EPUB:',dest)
if __name__=='__main__':main()
