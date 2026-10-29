"""Check the corrected PDF's data, structure, citations, margins and images."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import build_research_paper as builder


def main():
    path=ROOT/'output/pdf/IEEE_BTMS_Research_Paper_Formatted.pdf'
    document=pymupdf.open(path)
    content=builder.json_file(builder.CONTENT)
    blocks,refs=builder.renumber(content)
    tables=builder.recorded_tables(content)
    text='\n'.join(p.get_text() for p in document)
    normalized=' '.join(text.split())
    checks=[]
    def check(name,condition,detail=''):
        checks.append(dict(name=name,passed=bool(condition),detail=detail))
    check('All figures, tables and equations present exactly once',
          all(len(re.findall(rf'Fig\. {i}\.',text))==1 for i in range(1,7)) and
          all(len(re.findall(rf'TABLE {n}\.',text))==1 for n in tables) and
          all(len(re.findall(rf'(?m)^\({i}\)\s*$',text))==1 for i in range(1,12)) and
          not re.search(r'(?m)^\(12\)\s*$',text))
    rows=[]
    for numeral,table in tables.items():
        for row in table[2:]:
            expected=' '.join(builder.clean(cell) for cell in row)
            if expected not in normalized:rows.append(dict(table=numeral,row=row))
    check('Every printed table row matches recorded-data or declared-parameter source',not rows,str(rows))
    first_cites=[]
    for block in blocks:
        for match in re.finditer(r'\[(\d+)\]',block.get('text','')):
            n=int(match[1])
            if n not in first_cites:first_cites.append(n)
    ref_text=text.rsplit('REFERENCES',1)[1]
    pdf_numbers=[int(n) for n in re.findall(r'(?m)^\[(\d+)\]',ref_text)]
    check('Citations resolve and bibliography follows first appearance',
          first_cites==list(range(1,16)) and pdf_numbers==list(range(1,16)) and
          len({r.get('doi') or r['url'] for r in refs})==15,
          str(dict(first_citations=first_cites,bibliography=pdf_numbers)))
    check('Four recent primary-source references retained',
          sum(r.get('year',0)>=2025 for r in refs)==4 and
          all(r['checked']=='2026-10-27' for r in refs))
    old=['PID is the only safe raw baseline here','before drivetrain and BTMS losses',
         'of evaluated seconds','Equations (11) and (12)','24.94 kB','16.04 kB',
         'sampled benchmark inputs']
    check('Identified stale claims removed',not [s for s in old if s in normalized])
    check('Complete energy identity has one equation number',
          len(builder.EQUATIONS[11])==2 and 'Q_{\\mathrm{radiator}}' in builder.EQUATIONS[11][1])
    check('Exact grade formula and terminal target indicator present',
          '\\cos\\theta' in builder.EQUATIONS[1][0] and '\\sin\\theta' in builder.EQUATIONS[1][0] and
          '(1-d)' in builder.EQUATIONS[9][1])
    check('No inherited replacement glyphs or encoding artifacts',
          '\ufffd' not in text and not any(x in text for x in ('Ã¢','â€','Â°C')))
    boundaries=[]
    for number,page in enumerate(document,1):
        for word in page.get_text('words'):
            if word[0]<34 or word[2]>578 or word[1]<30 or word[3]>760:
                boundaries.append(dict(page=number,text=word[4],bounds=word[:4]))
    check('All text stays within review margins',not boundaries,str(boundaries[:20]))
    check('All pages have content',all(len(p.get_text().strip())>200 for p in document),f'{len(document)} pages')
    placements=[]
    for number in range(1,7):
        with Image.open(ROOT/f'report/paper_revision/figures/figure_{number}.png') as image:
            image_hash=hashlib.md5(image.convert('RGB').tobytes()).digest()
        images=[];captions=[]
        for page_number,page in enumerate(document,1):
            images += [(page_number,info['bbox']) for info in page.get_image_info(hashes=True)
                       if info['digest']==image_hash]
            captions += [(page_number,tuple(rect)) for rect in page.search_for(f'Fig. {number}.')]
        ok=(len(images)==1 and any(p==images[0][0] and abs(rect[0]-images[0][1][0])<5
                                  for p,rect in captions))
        placements.append(dict(figure=number,passed=ok,image=images,captions=captions))
    check('Every chart stays with its caption in the same page and column',
          all(r['passed'] for r in placements),str(placements))
    manifest=builder.json_file(ROOT/'report/paper_revision/build_manifest.json')
    changed=[]
    for group in ('input_sha256','figure_sha256'):
        for name,expected in manifest[group].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:changed.append(name)
    check('Built source/data/figure identities remain intact',not changed,str(changed))
    from btms.dashboard.evidence import aggregate,audit,get_runs,recorded_episodes
    episodes=recorded_episodes()
    evidence=audit(aggregate(episodes),episodes,get_runs())
    check('Episode-derived manuscript tables and retained evidence remain consistent',
          all(c['status']=='pass' for c in evidence['checks']))
    check('External submission requirements are disclosed',
          'Public repository/data/demo URLs have not yet been assigned or verified' in normalized and
          'venue-specific page limits' in normalized)
    out=ROOT/'report/paper_revision'
    render=out/'rendered';render.mkdir(exist_ok=True)
    for i,page in enumerate(document,1):
        page.get_pixmap(matrix=pymupdf.Matrix(1.6,1.6)).save(render/f'page-{i:02}.png')
    report=dict(checked_at=datetime.now(timezone.utc).isoformat(),pdf=str(path),pages=len(document),
                all_checks_pass=all(c['passed'] for c in checks),checks=checks,
                scope='Programmatic checks; rendered pages require separate visual inspection.',
                remaining=['No target venue or evaluator-facing public links supplied.',
                           'TeX source emitted and statically checked; no installed TeX engine was available for compilation.'])
    (out/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    if not report['all_checks_pass']:raise SystemExit(1)


if __name__=='__main__':main()
