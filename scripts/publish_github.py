"""Publish the reviewed submission via GitHub's API using standard Git credentials.

No access token is printed or persisted. Local git commit/push remain owned by
the session hook. This script is for an explicitly requested publication only.
"""
from pathlib import Path
import base64
import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'submission/github'
STATE=ROOT/'submission/GITHUB_PUBLICATION.json'
REPO='Harshit3929/rl-battery-thermal-management'
API='https://api.github.com/repos/'+REPO
TEXT={'.py','.md','.txt','.json','.csv','.yaml','.yml','.tex','.ps1','.sh','.html','.css','.js','.mjs'}

def blob_sha(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def main():
    env=dict(os.environ,GCM_INTERACTIVE='never',GIT_TERMINAL_PROMPT='0')
    result=subprocess.run(['git','credential-manager','get'],
                          input='protocol=https\nhost=github.com\nusername=Harshit3929\n\n',
                          text=True,capture_output=True,env=env,timeout=25)
    if result.returncode: raise RuntimeError('Standard Git credential manager did not return authentication')
    credentials=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    token=credentials.get('password')
    if not token: raise RuntimeError('GitHub authentication is required')

    def request(url,method='GET',data=None,authenticated=True,allow_missing=False):
        headers={'User-Agent':'RL-BTMS-Evaluator-Publication','Accept':'application/vnd.github+json',
                 'X-GitHub-Api-Version':'2022-11-28'}
        if authenticated: headers['Authorization']='Bearer '+token
        body=None if data is None else json.dumps(data,ensure_ascii=False).encode('utf-8')
        if body is not None:headers['Content-Type']='application/json'
        for attempt in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(url,data=body,headers=headers,method=method),timeout=60) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                if allow_missing and method=='GET' and exc.code in [404,409]:return None
                retry=exc.headers.get('Retry-After')
                if attempt<3 and (exc.code in [429,502,503,504] or (exc.code==403 and retry)):
                    time.sleep(min(int(retry or (5*(attempt+1))),55));continue
                raise RuntimeError(f'GitHub {method} returned HTTP {exc.code}: '+exc.read(600).decode('utf-8',errors='replace')) from None

    user=request('https://api.github.com/user')
    assert user['login']=='Harshit3929','Unexpected GitHub account'
    repo=request(API)
    assert repo['visibility']=='public' and repo['default_branch']=='main'
    manifest=json.loads((PACKAGE/'SHA256_MANIFEST.json').read_text())
    for row in manifest:
        data=(PACKAGE/row['path']).read_bytes()
        assert hashlib.sha256(data).hexdigest()==row['sha256'],row['path']
    paths=sorted([row['path'] for row in manifest]+['SHA256_MANIFEST.json'])
    state=json.loads(STATE.read_text()) if STATE.is_file() else {'repository':REPO,'blobs':{}}
    assert state['repository']==REPO

    def save():STATE.write_text(json.dumps(state,indent=2),encoding='utf-8')
    ref=request(API+'/git/ref/heads/main',allow_missing=True)
    if ref is None:
        seed=request(API+'/contents/README.md','PUT',{'message':'Initialize verified RL-BTMS project',
                      'content':base64.b64encode((PACKAGE/'README.md').read_bytes()).decode('ascii')})
        state['base_commit']=seed['commit']['sha'];save()
        ref=request(API+'/git/ref/heads/main')
    head=ref['object']['sha']
    if state.get('published_commit')==head:
        print('Repository already contains the published commit.',flush=True);return
    if 'base_commit' not in state:
        existing=request(API+'/git/trees/'+head+'?recursive=1')
        assert all(x['path']=='README.md' for x in existing['tree'] if x['type']=='blob'),'Review the existing repository before publishing'
        state['base_commit']=head;save()
    assert state['base_commit']==head,'Remote branch changed; review before retrying'
    parent=request(API+'/git/commits/'+head)
    entries=[];binary=[]
    for name in paths:
        data=(PACKAGE/name).read_bytes()
        entry={'path':name,'mode':'100644','type':'blob'}
        if Path(name).suffix in TEXT or name=='.gitignore':
            entry['content']=data.decode('utf-8');entries.append(entry)
        else:binary.append((name,data,entry))
    print(f'Publishing {len(paths)} files: {len(entries)} text files and {len(binary)} binary artifacts.',flush=True)
    for i,(name,data,entry) in enumerate(binary):
        expected=blob_sha(data)
        if state['blobs'].get(name)!=expected:
            uploaded=request(API+'/git/blobs','POST',{'content':base64.b64encode(data).decode('ascii'),'encoding':'base64'})
            assert uploaded['sha']==expected,name
            state['blobs'][name]=expected;save()
            time.sleep(1.05)
        entry['sha']=expected;entries.append(entry)
        if (i+1)%5==0 or i+1==len(binary):print(f'Binary artifacts: {i+1}/{len(binary)}',flush=True)
    tree=request(API+'/git/trees','POST',{'base_tree':parent['tree']['sha'],'tree':entries})
    state['tree_sha']=tree['sha'];save()
    commit=request(API+'/git/commits','POST',{'message':'Publish reproducible RL-BTMS implementation, trained policies and evaluation evidence',
                   'tree':tree['sha'],'parents':[head]})
    current=request(API+'/git/ref/heads/main')['object']['sha']
    assert current==head,'Remote changed during upload; review before publishing'
    request(API+'/git/refs/heads/main','PATCH',{'sha':commit['sha'],'force':False})
    state['published_commit']=commit['sha'];save()
    public_tree=request(API+'/git/trees/'+tree['sha']+'?recursive=1',authenticated=False)
    actual={x['path']:x['sha'] for x in public_tree['tree'] if x['type']=='blob'}
    expected={name:blob_sha((PACKAGE/name).read_bytes()) for name in paths}
    assert not public_tree.get('truncated') and actual==expected,'Remote file/hash verification failed'
    public_checks=[]
    for name in ['README.md','output/pdf/IEEE_BTMS_Research_Paper_Formatted.pdf',
                 'report/dashboard/screenshots/simulation-desktop.png']:
        url='https://raw.githubusercontent.com/'+REPO+'/main/'+urllib.parse.quote(name,safe='/')
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'RL-BTMS-Access-Check'}),timeout=45) as response:
            downloaded=response.read()
        assert hashlib.sha256(downloaded).hexdigest()==hashlib.sha256((PACKAGE/name).read_bytes()).hexdigest(),name
        public_checks.append({'path':name,'anonymous_download_matches':True})
    state.update({'published':True,'repository_url':'https://github.com/'+REPO,
                  'file_count':len(paths),'all_remote_blob_hashes_match':True,'anonymous_access_checks':public_checks,
                  'completed_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    save()
    print(json.dumps({k:v for k,v in state.items() if k!='blobs'},indent=2),flush=True)

if __name__=='__main__':main()
