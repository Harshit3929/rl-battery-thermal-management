"""Prepare explicit, hash-checked GitHub and Drive upload sets without publishing."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'submission'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    from btms.dashboard.evidence import build_evidence
    evidence=build_evidence()
    failed=[c['name'] for c in evidence['audit']['checks'] if c['status']=='fail']
    assert not failed, failed
    github=DEST/'github'
    drive=DEST/'drive'/'RL_BTMS_MidTerm_Evidence'
    github.mkdir(parents=True,exist_ok=True); drive.mkdir(parents=True,exist_ok=True)
    chosen={a['path'] for a in evidence['artifacts']}
    chosen.update(['.gitignore','PLAN.md','requirements-paper.txt','requirements-validation.txt',
                   'deliverables/WPR_Weeks_1_to_4.json',
                   'output/pdf/BTMS_Simulation_and_Viva_Guide.pdf','output/pdf/WPR_Weeks_1_to_4.pdf'])
    chosen.update(str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'scripts').glob('*') if p.is_file())
    chosen.update(str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'docs').glob('*.md'))
    chosen.update(str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'dashboard-qa').glob('*')
                  if p.is_file() and p.suffix in ['.js','.json','.mjs','.cjs'])
    chosen.update(str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'deliverables').glob('*')
                  if p.is_file() and p.suffix in ['.docx','.pptx'])
    chosen.add('report/dashboard/replays/index.json')
    for base in (ROOT/'outputs/study_20000').glob('*/*'):
        for name in ['evaluation_raw.json','evaluation_shielded.json']:
            chosen.add((base/name).relative_to(ROOT).as_posix())
        chosen.update(p.relative_to(ROOT).as_posix() for p in (base/'deployment').glob('*')
                      if p.is_file() and p.suffix in ['.onnx','.json'])
    records=[]
    secret_patterns=[re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
                     re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
                     re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
                     re.compile(r'\bsk-[A-Za-z0-9]{40,}\b')]
    for name in sorted(chosen):
        parts=Path(name).parts
        assert not any(part in ['Future-Ideas','.claude','.codex','.aws','.git','.venv','node_modules','__pycache__'] for part in parts)
        source=ROOT/name
        assert source.is_file(),name
        assert source.stat().st_size < 50_000_000,name
        if source.suffix in ['.py','.ps1','.sh','.yaml','.json','.md','.txt','.js','.html','.css','.tex']:
            text=source.read_text(encoding='utf-8-sig',errors='replace')
            assert not any(p.search(text) for p in secret_patterns),f'Potential secret in {name}'
        target=github/name; target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,target)
        records.append({'path':name,'bytes':source.stat().st_size,'sha256':sha(source)})
    (github/'report/dashboard/evidence.json').write_text(json.dumps(evidence,indent=2,allow_nan=False),encoding='utf-8')
    records.append({'path':'report/dashboard/evidence.json','bytes':(github/'report/dashboard/evidence.json').stat().st_size,
                    'sha256':sha(github/'report/dashboard/evidence.json')})
    drive_map={
      'docs/EVALUATOR_README.md':'00_START_HERE.md',
      'output/pdf/IEEE_BTMS_Research_Paper_Formatted.pdf':'01_Technical_Documentation/Research_Paper_Canonical.pdf',
      'output/pdf/BTMS_Simulation_and_Viva_Guide.pdf':'01_Technical_Documentation/Simulation_and_Viva_Guide.pdf',
      'output/pdf/WPR_Weeks_1_to_4.pdf':'01_Technical_Documentation/WPR_Weeks_1_to_4.pdf',
      'docs/ARCHITECTURE.md':'01_Technical_Documentation/Architecture.md',
      'docs/IMPLEMENTATION_STATUS.md':'01_Technical_Documentation/Implementation_Status.md',
      'docs/PAPER_EVIDENCE_AUDIT.md':'01_Technical_Documentation/Paper_Evidence_Audit.md',
      'docs/DASHBOARD.md':'01_Technical_Documentation/Dashboard_Instructions.md',
      'deliverables/IEEE_BTMS_References.json':'01_Technical_Documentation/Verified_References.json',
    }
    for p in (ROOT/'report/dashboard/screenshots').glob('*.png'):
        drive_map[p.relative_to(ROOT).as_posix()]='02_Dashboard_Screenshots/'+p.name
    for p in (ROOT/'report/results').glob('*'):
        if p.suffix in ['.csv','.png','.json']:
            drive_map[p.relative_to(ROOT).as_posix()]='03_Experimental_Results/'+p.name
    for name in ['test_report.json','reproduction.json','browser_test.json','mpc_spotcheck.json','static_test.json']:
        drive_map['report/dashboard/'+name]='04_Testing_and_Validation/'+name
    for name in ['validation.json','visual_review.json','build_manifest.json']:
        drive_map['report/paper_revision/'+name]='04_Testing_and_Validation/paper_'+name
    for p in (ROOT/'deliverables').glob('*'):
        if p.suffix in ['.docx','.pptx']:
            drive_map[p.relative_to(ROOT).as_posix()]='05_Supplementary_Reports_and_Slides/'+p.name
    for source_name,destination in drive_map.items():
        source=ROOT/source_name; target=drive/destination
        target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,target)
    portable=ROOT/'deliverables/RL_Battery_Lab_Evidence.zip'
    if portable.is_file():
        target=drive/'06_Portable_Recorded_Demo'/portable.name
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(portable,target)
    (drive/'00_READ_ME.txt').write_text(
        'RL-BTMS mid-term evidence\n\nStart with 00_START_HERE.md and the canonical paper.\n'
        'Dashboard screenshots are retained actual captures from 27 October 2026.\n'
        'Temperatures and cooling electricity are simulation outputs, not physical measurements.\n'
        'The portable demo is a recorded evidence viewer; fresh runs require the Python source/models.\n'
        'Supplementary DOCX/PPTX files have structural checks; review their layout in Office.\n'
        'The WPR uses retrospective grouping; its reporting dates are unconfirmed.\n'
        'The GitHub repository and Google Drive share URLs remain pending creation/access verification.\n',encoding='utf-8')
    for label,directory in [('github',github),('drive',drive)]:
        manifest=[{'path':p.relative_to(directory).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
                  for p in sorted(directory.rglob('*')) if p.is_file() and p.name!='SHA256_MANIFEST.json']
        (directory/'SHA256_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        archive=DEST/('RL_BTMS_GitHub_Upload.zip' if label=='github' else 'RL_BTMS_Google_Drive_Evidence.zip')
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(directory.rglob('*')):
                if p.is_file():z.write(p,p.relative_to(directory).as_posix())
        with zipfile.ZipFile(archive) as z: assert z.testzip() is None
    summary={'prepared_at':datetime.now(timezone.utc).isoformat(),'published':False,'public_urls':{},
             'github_files':len(records),'github_bytes':sum(r['bytes'] for r in records),
             'drive_files':len(drive_map)+2+int(portable.is_file()),
             'evidence_audit_checks':evidence['audit']['checks'],
             'excluded':'Python environment, caches, logs, old paper drafts, replay buffers, credentials and private tool settings',
             'archives':[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(DEST.glob('*.zip'))]}
    (DEST/'PREPARATION_STATUS.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='evidence_audit_checks'},indent=2))

if __name__=='__main__':
    main()
