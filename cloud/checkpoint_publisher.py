"""Trusted checkpoint/Telegram broker, separate from model-tool credentials."""
from pathlib import Path
import base64, ctypes, hashlib, json, os, time
import urllib.request, urllib.error

ROOT=Path(__file__).resolve().parent.parent
REPO=os.environ['GITHUB_REPOSITORY']; RUN=os.environ['GITHUB_RUN_ID']
HEADERS={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'test-4-checkpoints'}
TOKEN=os.environ.get('TELEGRAM_BOT_TOKEN'); CHAT=os.environ.get('TELEGRAM_CHAT_ID')
BRANCH='progress/run-'+RUN
try: ctypes.CDLL(None).prctl(4,0,0,0,0)
except Exception: pass
blob_cache={}; published={}; head=None; tree_sha=None; message_id=None; previous_message=None

def api(path,payload=None,method=None):
    req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,
        data=None if payload is None else json.dumps(payload).encode(),headers=HEADERS,
        method=method or ('GET' if payload is None else 'POST'))
    with urllib.request.urlopen(req,timeout=30) as response: return json.load(response)

def load(name):
    try: return json.loads((ROOT/'output'/name).read_text(encoding='utf-8'))
    except (FileNotFoundError,ValueError): return {}

def notify(final):
    global message_id,previous_message
    if not TOKEN or not CHAT: return
    usage=load('usage.json'); states=load('status.json')
    lines=['test-4 / DeepSeek — '+('контрольная точка завершения' if final else 'работает в облаке'),
           'API: $'+str(usage.get('confirmed_usd','0'))+' подтверждено; $'+str(usage.get('reserved_usd','0'))+' зарезервировано',
           'Запросов учтено: '+str(len(usage.get('calls',[])))]
    for role,state in states.items():
        lines.append(role+': '+str(state.get('event','?'))+' '+str(state.get('summary',''))[:120])
    if usage.get('stop_reason'): lines.append('Остановка: '+str(usage['stop_reason']))
    lines.extend(['Прогресс: https://github.com/'+REPO+'/tree/'+BRANCH,
                  'Лог: https://github.com/'+REPO+'/actions/runs/'+RUN])
    text='\n'.join(lines)[:3900]
    if text==previous_message: return
    payload={'chat_id':CHAT,'text':text,'disable_web_page_preview':True}
    method='sendMessage' if message_id is None else 'editMessageText'
    if message_id is not None: payload['message_id']=message_id
    req=urllib.request.Request('https://api.telegram.org/bot'+TOKEN+'/'+method,
        data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as response: result=json.load(response)
    if result.get('ok'):
        message_id=result['result'].get('message_id',message_id); previous_message=text

def snapshot():
    global head,tree_sha,published
    files={}; suffixes={'.lean','.toml','.json','.md','.py','.m','.csv','.svg','.png','.pdf','.log'}
    for folder in ['lean','simulation','research/notes','review','reports']:
        for path in (ROOT/folder).rglob('*'):
            relative=path.relative_to(ROOT)
            if path.is_symlink() or not path.is_file() or any(p in {'.lake','.home','__pycache__','.git','raw'} for p in relative.parts): continue
            if path.suffix not in suffixes and path.name!='lean-toolchain': continue
            if path.suffix=='.pdf' and folder!='reports': continue
            if path.stat().st_size<=8_000_000: files['checkpoint/'+relative.as_posix()]=path.read_bytes()
    for name in ['usage.json','status.json','run-summary.json']:
        path=ROOT/'output'/name
        if path.is_file(): files['checkpoint/run/'+name]=path.read_bytes()
    hashes={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
    changed=[name for name,digest in hashes.items() if published.get(name)!=digest]
    removed=set(published)-set(hashes)
    if not changed and not removed: return
    if head is None:
        try: head=api('git/ref/heads/'+BRANCH)['object']['sha']
        except urllib.error.HTTPError as error:
            if error.code!=404: raise
            head=api('git/ref/heads/main')['object']['sha']
            api('git/refs',{'ref':'refs/heads/'+BRANCH,'sha':head})
        tree_sha=api('git/commits/'+head)['tree']['sha']
    entries=[]
    for name in changed:
        digest=hashes[name]; sha=blob_cache.get(digest)
        if sha is None:
            sha=api('git/blobs',{'content':base64.b64encode(files[name]).decode(),'encoding':'base64'})['sha']
            blob_cache[digest]=sha; time.sleep(.9)
        entries.append({'path':name,'mode':'100644','type':'blob','sha':sha})
    entries.extend({'path':name,'mode':'100644','type':'blob','sha':None} for name in removed)
    tree=api('git/trees',{'base_tree':tree_sha,'tree':entries})['sha']
    commit=api('git/commits',{'message':'Checkpoint authored work and accounting: '+RUN,'tree':tree,'parents':[head]})['sha']
    api('git/refs/heads/'+BRANCH,{'sha':commit,'force':False},method='PATCH')
    head,tree_sha,published=commit,tree,hashes
    print('Published checkpoint:',len(changed),'changed files; books/chats/secrets excluded.',flush=True)

if __name__=='__main__':
    while True:
        final=(ROOT/'output/publisher.stop').exists()
        for operation in [lambda:notify(final),snapshot]:
            try: operation()
            except Exception as error: print('Broker retry next cycle:',type(error).__name__,getattr(error,'code',''),flush=True)
        if final: break
        for _ in range(90):
            if (ROOT/'output/publisher.stop').exists(): break
            time.sleep(1)
