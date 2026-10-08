#!/usr/bin/env python3
"""Local, append-only task memory. Records are data, never instructions."""
from __future__ import annotations
import argparse, contextlib, datetime as dt, hashlib, json, os, re, subprocess, sys, tempfile, time, uuid
from pathlib import Path

MAX_IN=32768; MAX_OUT=8192; MAX_TEXT=1200
STATUSES={"in_progress","blocked","completed","handed_off"}
KINDS={"decision","fact","lesson"}
SECRET=re.compile(r"(?i)(password\s*[:=]|api[_ -]?key\s*[:=]|bearer\s+[a-z0-9._-]{8,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|(?<!\w)\+?\d[\d() .-]{7,}\d(?!\w)|\b\d{14}\b)")
UUID_VALUE=re.compile(r"(?i)[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
SENSITIVE_KEYS=re.compile(r"(?i)(password|secret|token|credential|phone|email|birth.?date|passport|iin|diagnosis|complaint|prescription|allerg(y|ies)|patient.?name|first.?name|last.?name|doc.?number|icd.?10)")
class MemError(Exception): pass

def git(*args, cwd=None):
    try: return subprocess.check_output(["git",*args],cwd=cwd,stderr=subprocess.DEVNULL,text=True).strip()
    except (OSError,subprocess.CalledProcessError): raise MemError("git repository operation failed")
def context():
    root=Path(git("rev-parse","--show-toplevel")).resolve(); common=Path(git("rev-parse","--path-format=absolute","--git-common-dir",cwd=root)).resolve()
    base=common/"devbrain-memory"/"v1"; guard_store(base)
    return root,base
def guard_store(base):
    # Refuse symlink/reparse components; only create absent descendants after checking parents.
    cur=Path(base.anchor)
    for part in Path(base).parts[1:]:
        cur=cur/part
        if cur.exists() and (cur.is_symlink() or getattr(cur.lstat(),"st_file_attributes",0)&0x400): raise MemError("memory store path rejected")
    base.mkdir(parents=True,exist_ok=True)
    real=base.resolve()
    if real != base.absolute(): raise MemError("memory store path rejected")
    for child in base.iterdir():
        if child.is_symlink() or getattr(child.lstat(),"st_file_attributes",0)&0x400: raise MemError("memory store child rejected")

@contextlib.contextmanager
def locked(base):
    guard_store(base); p=base/".lock"
    fd=os.open(p,os.O_CREAT|os.O_RDWR,0o600)
    f=os.fdopen(fd,"r+b",buffering=0); acquired=False; deadline=time.monotonic()+2
    try:
        if os.fstat(f.fileno()).st_size==0:
            f.write(b"0"); os.fsync(f.fileno())
        while True:
            try:
                if os.name=="nt":
                    import msvcrt
                    f.seek(0); msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                acquired=True; break
            except OSError:
                if time.monotonic()>=deadline: raise MemError("memory store lock timed out")
                time.sleep(.02)
        yield
    finally:
        if acquired:
            try:
                if os.name=="nt":
                    import msvcrt
                    f.seek(0); msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(),fcntl.LOCK_UN)
            except OSError: pass
        f.close()

def compact(x): return json.dumps(x,ensure_ascii=False,separators=(",",":"))
def atomic(path,obj):
    guard_store(path.parent.parent)
    path.parent.mkdir(exist_ok=True)
    if path.parent.is_symlink(): raise MemError("memory store child rejected")
    if path.exists(): raise MemError("immutable record already exists")
    fd,tmp=tempfile.mkstemp(prefix=".tmp-",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="\n") as f: f.write(compact(obj)); f.flush(); os.fsync(f.fileno())
        if path.exists(): raise MemError("immutable record already exists")
        os.replace(tmp,path)
    finally:
        with contextlib.suppress(FileNotFoundError): os.unlink(tmp)
def records(base):
    folder=base/"records"; guard_store(base); folder.mkdir(exist_ok=True)
    if folder.is_symlink(): raise MemError("memory store child rejected")
    out=[]; errors=[]
    for p in sorted(folder.glob("*.json")):
        try:
            if p.is_symlink() or getattr(p.lstat(),"st_file_attributes",0)&0x400: raise ValueError
            if p.stat().st_size>65536: raise ValueError
            with p.open("rb") as stream: raw=stream.read(65537)
            if len(raw)>65536: raise ValueError
            r=json.loads(raw.decode("utf-8"))
            expected={"event_id","task_id","revision","parent_event_id","created_at","worktree","branch","head","checkpoint","knowledge","idempotency_key","request_digest"}
            if not isinstance(r,dict) or set(r)!=expected or not isinstance(r.get("event_id"),str) or r["event_id"]!=p.stem or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}",r["event_id"]): raise ValueError
            if not isinstance(r.get("task_id"),str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}",r["task_id"]): raise ValueError
            if not isinstance(r.get("revision"),int) or isinstance(r["revision"],bool) or r["revision"]<1: raise ValueError
            if r.get("parent_event_id") is not None and not isinstance(r.get("parent_event_id"),str): raise ValueError
            if any(not isinstance(r.get(k),str) for k in ("created_at","worktree","branch","head")): raise ValueError
            if checkpoint_data(r["checkpoint"])!=r["checkpoint"]: raise ValueError
            if not isinstance(r["knowledge"],list) or len(r["knowledge"])>3 or any(not stored_knowledge_valid(item) for item in r["knowledge"]): raise ValueError
            if r["idempotency_key"] is not None and not isinstance(r["idempotency_key"],str): raise ValueError
            if r["request_digest"] is not None and (not isinstance(r["request_digest"],str) or not re.fullmatch(r"[0-9a-f]{64}",r["request_digest"])): raise ValueError
            out.append(r)
        except Exception: errors.append(p.name)
    chains={}
    for row in out:
        if isinstance(row.get("task_id"),str) and isinstance(row.get("revision"),int): chains.setdefault(row["task_id"],[]).append(row["revision"])
    for task,nums in chains.items():
        task_rows=sorted((r for r in out if r.get("task_id")==task),key=lambda r:r.get("revision",0))
        parent=None; valid=sorted(nums)==list(range(1,len(nums)+1))
        for row in task_rows:
            if row.get("parent_event_id")!=parent: valid=False
            parent=row.get("event_id")
        if not valid: errors.append("task-chain:"+task)
    return out,errors
def stored_knowledge_valid(item):
    fields={"schema_version","id","key","kind","topic","summary","tags","scope","source_type","evidence_summary","anchors","supersedes"}
    if not isinstance(item,dict) or set(item)!=fields or item.get("schema_version")!=1 or item.get("kind") not in KINDS: return False
    if any(not isinstance(item.get(k),str) or len(item[k])>limit for k,limit in (("id",128),("key",128),("topic",128),("summary",MAX_TEXT),("evidence_summary",MAX_TEXT))): return False
    if item.get("scope") not in {"repo","task","worktree"} or item.get("source_type") not in {"source","test","documentation","user_evidence","derived"}: return False
    if item["kind"]=="decision" and item["source_type"]!="user_evidence": return False
    if item["kind"]!="decision" and not item.get("anchors"): return False
    if not isinstance(item.get("tags"),list) or len(item["tags"])>12 or any(not isinstance(tag,str) or len(tag)>64 for tag in item["tags"]): return False
    if not isinstance(item.get("supersedes"),list) or any(not isinstance(ref,str) or len(ref)>128 for ref in item["supersedes"]): return False
    if not isinstance(item.get("anchors"),list) or len(item["anchors"])>8: return False
    for anchor in item["anchors"]:
        if not isinstance(anchor,dict) or set(anchor)!={"path","sha256","state","worktree"}: return False
        if not isinstance(anchor["path"],str) or anchor["state"] not in {"sources_match","worktree_only"}: return False
        if not isinstance(anchor["sha256"],str) or not re.fullmatch(r"[0-9a-f]{64}",anchor["sha256"]): return False
        if anchor["worktree"] is not None and not isinstance(anchor["worktree"],str): return False
    return True
def read_payload(raw):
    if len(raw)>MAX_IN: raise MemError("input exceeds 32 KB")
    try: x=json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError,ValueError): raise MemError("input must be UTF-8 JSON")
    if not isinstance(x,dict): raise MemError("input must be an object")
    def scan(v,k=""):
        if SENSITIVE_KEYS.search(k): raise MemError("sensitive payload field rejected")
        if isinstance(v,dict):
            for a,b in v.items(): scan(b,str(a))
        elif isinstance(v,list):
            for a in v: scan(a,k)
        elif isinstance(v,str) and not UUID_VALUE.fullmatch(v) and SECRET.search(v): raise MemError("sensitive payload content rejected")
    scan(x); return x
def txt(v,label,limit=MAX_TEXT,empty=True):
    if not isinstance(v,str) or len(v)>limit or (not empty and not v): raise MemError("invalid "+label)
    return v
def ident(v,label):
    if not isinstance(v,str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}",v): raise MemError("invalid "+label)
    return v
def anchor_relative(root,s):
    if not isinstance(s,str) or Path(s).is_absolute() or any(part in {".",".."} for part in Path(s).parts): raise MemError("anchor path rejected")
    rel=Path(s).as_posix()
    path_parts=Path(rel).parts
    if not rel or not path_parts or "\\" in s or ":" in s: raise MemError("anchor path rejected")
    parts=[x.lower() for x in path_parts]; name=parts[-1]
    blocked={".git",".venv","venv","node_modules","storage","uploads","upload","backup","backups","dumps","output","test-results","transcript","transcripts","credential","credentials","secret","secrets","token","tokens","patients","patient","patient-data","phi"}
    # Schema/source filenames may describe token handling without containing credential data.
    if any(a in blocked or a.startswith(".env") for a in parts) or any(w in name for w in ("credential","secret","backup","dump","transcript")) or Path(name).suffix.lower() in {".pem",".key",".sql",".dump"}: raise MemError("anchor path rejected")
    return rel
def no_anchor(root,s):
    rel=anchor_relative(root,s); p=root/rel
    try: resolved=p.resolve(strict=True)
    except OSError: raise MemError("anchor path rejected")
    if root not in resolved.parents or not resolved.is_file(): raise MemError("anchor path rejected")
    actual=resolved.relative_to(root).as_posix()
    return resolved,actual
def anchor_meta(root,items):
    if not isinstance(items,list) or len(items)>8: raise MemError("invalid anchors")
    result=[]
    for x in items:
        if isinstance(x,dict): x=x.get("path")
        p,rel=no_anchor(root,x)
        digest=hashlib.sha256()
        with p.open("rb") as source:
            for chunk in iter(lambda: source.read(1024*1024),b""): digest.update(chunk)
        h=digest.hexdigest(); dirty=bool(git("status","--porcelain","--untracked-files=all","--ignored=matching","--",rel,cwd=root))
        result.append({"path":rel,"sha256":h,"state":"worktree_only" if dirty else "sources_match","worktree":str(root) if dirty else None})
    return result
SEARCH_STOPWORDS={"a","an","and","are","as","at","be","by","do","does","for","from","how","in","is","it","of","on","or","the","this","to","was","what","when","where","which","with","и","или","в","на","для","по","из","с","к","что","как","это"}
def norm(s): return set(re.findall(r"[^\W_]+",s.casefold(),flags=re.UNICODE))
def search_terms(s): return norm(s)-SEARCH_STOPWORDS
def knowledge_item(x,root):
    required={"schema_version","id","key","kind","topic","summary","tags","scope","source_type","evidence_summary","anchors","supersedes"}
    if not isinstance(x,dict) or set(x)!=required: raise MemError("invalid knowledge schema")
    if x["schema_version"]!=1 or x["kind"] not in KINDS: raise MemError("invalid knowledge schema")
    out=dict(x)
    for k in ("id","key","topic","scope","source_type"): out[k]=txt(x[k],k,128,False)
    if out["scope"] not in {"repo","task","worktree"} or out["source_type"] not in {"source","test","documentation","user_evidence","derived"}: raise MemError("invalid knowledge scope")
    if out["kind"]=="decision" and out["source_type"]!="user_evidence": raise MemError("decisions require user evidence")
    out["summary"]=txt(x["summary"],"summary")
    out["evidence_summary"]=txt(x["evidence_summary"],"evidence_summary")
    if not isinstance(x["tags"],list) or len(x["tags"])>12 or any(not isinstance(t,str) or len(t)>64 for t in x["tags"]): raise MemError("invalid tags")
    if not isinstance(x["supersedes"],list) or any(not isinstance(t,str) or len(t)>128 for t in x["supersedes"]): raise MemError("invalid supersedes")
    out["anchors"]=anchor_meta(root,x["anchors"])
    if out["kind"]!="decision" and not out["anchors"]: raise MemError("source-backed knowledge requires an anchor")
    if any(a["state"]=="worktree_only" for a in out["anchors"]): out["scope"]="worktree"
    return out
def task_chain(rows,task):
    ev=sorted((e for e in rows if e.get("task_id")==task),key=lambda e:e.get("revision",0))
    if not ev: return None,True
    parent=None
    for index,e in enumerate(ev,1):
        if e.get("revision")!=index or e.get("parent_event_id")!=parent: return None,False
        parent=e.get("event_id")
    return ev[-1],True
def latest_task(rows,task):
    return task_chain(rows,task)[0]
def append_event(base,event):
    path=base/"records"/(event["event_id"]+".json"); atomic(path,event)
def new_event(root,task,rev,checkpoint,know,idem=None,parent=None,digest=None):
    return {"event_id":str(uuid.uuid4()),"task_id":task,"revision":rev,"parent_event_id":parent,"created_at":dt.datetime.now(dt.timezone.utc).isoformat(),"worktree":str(root),"branch":git("branch","--show-current",cwd=root),"head":git("rev-parse","HEAD",cwd=root),"checkpoint":checkpoint,"knowledge":know,"idempotency_key":idem,"request_digest":digest}
def checkpoint_data(x,old=None):
    fields=("goal","status","allowed_paths","denied_paths","completed","next_step","blockers","artifacts","validation_reported")
    defaults={"goal":"","status":"in_progress","allowed_paths":[],"denied_paths":[],"completed":[],"next_step":"","blockers":[],"artifacts":[],"validation_reported":False}
    cp={k:x.get(k,old.get(k,defaults[k]) if old else defaults[k]) for k in fields}
    cp["goal"]=txt(cp["goal"],"goal");
    if cp["status"] not in STATUSES: raise MemError("invalid checkpoint status")
    for k in ("allowed_paths","denied_paths","completed","blockers","artifacts"):
        if not isinstance(cp[k],list) or len(cp[k])>20 or any(not isinstance(v,str) or len(v)>300 for v in cp[k]): raise MemError("invalid checkpoint field")
    cp["next_step"]=txt(cp["next_step"],"next_step")
    if not isinstance(cp["validation_reported"],(bool,str,dict,list)): raise MemError("invalid checkpoint field")
    if len(compact(cp).encode("utf-8"))>2600: raise MemError("checkpoint exceeds size limit")
    return cp
def source_state(root,a):
    try:
        p,rel=no_anchor(root,a["path"])
        if a.get("state")=="worktree_only": return "worktree_only"
        if a.get("worktree") and Path(a["worktree"]).resolve()!=root: return "worktree_only"
        current=hashlib.sha256(p.read_bytes()).hexdigest()
        dirty=bool(git("status","--porcelain","--untracked-files=all","--ignored=matching","--",rel,cwd=root))
        if dirty: return "worktree_only"
        return "sources_match" if current==a.get("sha256") else "source_changed"
    except Exception: return "source_missing"

def curated_records(root):
    """Read portable, tracked knowledge. Hashes in the file are author-pinned."""
    path=root/"docs"/"devbrain"/"memory"/"curated.json"
    try:
        if not path.exists() and not path.is_symlink(): return [],[]
        if path.is_symlink() or getattr(path.lstat(),"st_file_attributes",0)&0x400: return [],["curated.json:path_rejected"]
        resolved=path.resolve(strict=True)
        if root not in resolved.parents or not resolved.is_file(): return [],["curated.json:path_rejected"]
        if resolved.stat().st_size>65536: return [],["curated.json:oversized"]
        raw=resolved.read_bytes()
        data=json.loads(raw.decode("utf-8"))
        if not isinstance(data,dict) or set(data)!={"schema_version","knowledge"} or data["schema_version"]!=1: raise ValueError
        source=data["knowledge"]
        if not isinstance(source,list) or len(source)>100: raise ValueError
        try: curated_dirty=bool(git("status","--porcelain","--untracked-files=all","--ignored=matching","--","docs/devbrain/memory/curated.json",cwd=root))
        except MemError: curated_dirty=True
        result=[]; seen=set()
        required={"schema_version","id","key","kind","topic","summary","tags","scope","source_type","evidence_summary","anchors","supersedes"}
        for item in source:
            if not isinstance(item,dict) or set(item)!=required or item.get("kind") not in {"fact","lesson"} or item.get("scope")!="repo": raise ValueError
            if not isinstance(item.get("anchors"),list) or not item["anchors"] or len(item["anchors"])>8: raise ValueError
            anchors=[]
            for anchor in item["anchors"]:
                if not isinstance(anchor,dict) or set(anchor)!={"path","sha256"} or not isinstance(anchor.get("sha256"),str) or not re.fullmatch(r"[0-9a-f]{64}",anchor["sha256"]): raise ValueError
                rel=anchor_relative(root,anchor["path"])
                if rel!=anchor["path"]: raise ValueError
                target=root/rel
                if target.exists() or target.is_symlink(): no_anchor(root,rel)
                else:
                    parent=root
                    for part in Path(rel).parts[:-1]:
                        parent=parent/part
                        if not parent.exists() and not parent.is_symlink(): break
                        resolved=parent.resolve(strict=True)
                        if root not in resolved.parents: raise ValueError
                anchors.append({"path":rel,"sha256":anchor["sha256"],"state":"sources_match","worktree":None})
            clean=dict(item); clean["anchors"]=anchors
            if curated_dirty:
                clean["scope"]="worktree"
                for anchor in clean["anchors"]: anchor["state"]="worktree_only"
            if not stored_knowledge_valid(clean): raise ValueError
            if clean["id"] in seen: raise ValueError
            seen.add(clean["id"])
            for value in (clean["key"],clean["topic"],clean["summary"],clean["evidence_summary"],*clean["tags"]):
                if SECRET.search(value): raise ValueError
            result.append(clean)
        return result,[]
    except Exception:
        return [],["curated.json:invalid"]
def ranking(item,terms):
    words=norm(" ".join([item.get("key",""),item.get("topic",""),item.get("summary","")," ".join(item.get("tags",[]))," ".join(a.get("path","") for a in item.get("anchors",[]))]))
    return len(words&terms)
def status(root,base):
    rows,err=records(base); curated,curated_err=curated_records(root); errors=err+curated_err
    return {"status":"DEGRADED" if errors else "OK","event_count":len(rows),"corrupt_count":len(err),"curated_count":len(curated),"errors":errors[:20]}
def main():
    if hasattr(sys.stdout,"reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    ap=argparse.ArgumentParser(); ap.add_argument("action",choices=["begin","recall","capture","status","export"]); ap.add_argument("--task-id"); ap.add_argument("--query",default=""); ap.add_argument("--topics",default=""); ap.add_argument("--input-file"); ap.add_argument("--json",action="store_true"); args=ap.parse_args()
    try:
        root,base=context()
        if args.action=="capture" or (args.action=="begin" and args.input_file):
            if args.input_file:
                p=Path(args.input_file).resolve(strict=True)
                with p.open("rb") as stream: raw=stream.read(MAX_IN+1)
            else: raw=sys.stdin.buffer.read(MAX_IN+1)
            x=read_payload(raw)
        else: x={}
        if args.action=="status": out=status(root,base)
        elif args.action=="begin":
            query=x.get("query",args.query); topics=x.get("topics",args.topics)
            cp=checkpoint_data({"goal":x.get("goal") or args.query,"status":"in_progress"})
            begin_digest=hashlib.sha256(compact({"goal":cp["goal"],"query":query,"topics":topics}).encode("utf-8")).hexdigest()
            supplied_idem=ident(x["idempotency_key"],"idempotency_key") if x.get("idempotency_key") is not None else None
            begin_idem="begin:"+supplied_idem if supplied_idem else None
            with locked(base):
                rows,errors=records(base)
                prior=next((e for e in rows if begin_idem and e.get("idempotency_key")==begin_idem),None)
                if prior:
                    if prior.get("request_digest")!=begin_digest: raise MemError("idempotency key content mismatch")
                    task=prior["task_id"]; current=latest_task(rows,task)
                    if current is None: raise MemError("task revision chain invalid")
                    created=False
                else:
                    task=str(uuid.uuid4()); created=True
                    append_event(base,new_event(root,task,1,cp,[],begin_idem,digest=begin_digest))
                    current={"revision":1,"checkpoint":cp}
            out={"result":"OK" if created else "NOOP","task_id":task,"revision":current["revision"],"checkpoint":current["checkpoint"],"recall":recall(root,base,{"query":query,"topics":topics},include_active_tasks=False)}
        elif args.action=="capture": out=capture(root,base,x)
        elif args.action=="recall": out=recall(root,base,{"task_id":args.task_id,"query":args.query,"topics":args.topics})
        else: out=export(root,base)
        print(bound(out)); return 0
    except MemError as e: print(compact({"error":str(e)}),file=sys.stderr); return 2
    except Exception: print(compact({"error":"memory operation failed"}),file=sys.stderr); return 2
def capture(root,base,x):
    task=ident(x.get("task_id"),"task_id"); expected=x.get("expected_revision")
    if not isinstance(expected,int) or expected<0: raise MemError("invalid expected_revision")
    know=x.get("knowledge",[])
    if not isinstance(know,list) or len(know)>3: raise MemError("invalid knowledge")
    idem=x.get("idempotency_key")
    if idem is not None: idem=ident(idem,"idempotency_key")
    digest=hashlib.sha256(compact({"checkpoint":x.get("checkpoint",{}),"knowledge":know}).encode("utf-8")).hexdigest()
    with locked(base):
        rows,errs=records(base); current,valid=task_chain(rows,task)
        if not valid: raise MemError("task revision chain invalid")
        rev=current.get("revision",0) if current else 0
        if idem:
            prior=next((e for e in rows if e.get("task_id")==task and e.get("idempotency_key")==idem),None)
            if prior:
                if prior.get("request_digest")==digest: return {"result":"NOOP","revision":rev,"operation_revision":prior["revision"]}
                raise MemError("idempotency key content mismatch")
        if expected!=rev: return {"result":"CONFLICT","current_revision":rev}
        clean=[knowledge_item(k,root) for k in know]
        known={}
        for e in rows:
            for item in e.get("knowledge",[]): known.setdefault(item.get("id"),[]).append(item)
        curated,curated_errors=curated_records(root)
        if curated_errors: raise MemError("curated memory unavailable")
        for item in curated: known.setdefault(item.get("id"),[]).append(item)
        clean_ids=set()
        for item in clean:
            if item.get("id") in clean_ids: raise MemError("duplicate knowledge id in request")
            clean_ids.add(item.get("id"))
            previous=known.get(item.get("id"),[])
            if previous and any(old!=item for old in previous): raise MemError("knowledge id content conflict")
            for ref in item["supersedes"]:
                previous=known.get(ref,[])
                if not previous: raise MemError("unknown supersedes reference")
                if len({old.get("key") for old in previous})!=1: raise MemError("ambiguous supersedes reference")
                if previous[0].get("key")!=item.get("key"): raise MemError("supersedes key mismatch")
        cp=checkpoint_data(x.get("checkpoint",{}),current.get("checkpoint") if current else None)
        ev=new_event(root,task,rev+1,cp,clean,idem,current.get("event_id") if current else None,digest); append_event(base,ev); return {"result":"OK","revision":rev+1,"event_id":ev["event_id"]}
def recall(root,base,q,include_active_tasks=True):
    rows,errs=records(base); curated,curated_err=curated_records(root); errs.extend(curated_err); task=q.get("task_id")
    if task is not None: ident(task,"task_id")
    task_event,task_valid=task_chain(rows,task) if task is not None else (None,True)
    invalid=bool(task is not None and not task_valid)
    query_text=str(q.get("query",""))+" "+str(q.get("topics",""))
    if task_event:
        checkpoint=task_event.get("checkpoint",{})
        goal=checkpoint.get("goal","") if isinstance(checkpoint,dict) else ""
        query_text+=" "+str(goal)
    terms=search_terms(query_text)
    selected=[e for e in rows if task is None or e.get("task_id")==task or any(k.get("scope")=="repo" for k in e.get("knowledge",[]))]
    candidates=[]; latest_by_key={}
    sources=[(e,k,"local") for e in selected for k in e.get("knowledge",[])] + [(None,k,"curated") for k in curated]
    for e,k,origin in sources:
        if task is not None and e and e.get("task_id")!=task and k.get("scope")!="repo": continue
        if not task and k.get("scope")=="task": continue
        state=[source_state(root,a) for a in k.get("anchors",[])]
        if k.get("scope")=="worktree" and e and e.get("worktree"):
            try:
                if Path(e["worktree"]).resolve()!=root: state.append("worktree_only")
            except OSError: state.append("worktree_only")
        k=dict(k); k["provenance_state"]="source_changed" if "source_changed" in state else ("source_missing" if "source_missing" in state else ("worktree_only" if "worktree_only" in state else "sources_match"))
        k["origin"]=origin; k["_task_id"]=e.get("task_id") if e else None
        k["current_assertion"]=k["provenance_state"]=="sources_match" and k.get("scope")=="repo" and k.get("kind") in {"fact","lesson"} and bool(k.get("anchors"))
        if k["provenance_state"] in ("source_changed","source_missing"):
            k.pop("summary",None); k["summary_omitted"]=True
        if k["provenance_state"]=="worktree_only": k["scope"]="worktree"
        k["_rank_words"]=" ".join([k.get("key",""),k.get("topic",""),k.get("summary","")," ".join(k.get("tags",[]))," ".join(a.get("path","") for a in k.get("anchors",[]))])
        latest_by_key.setdefault(k.get("key"),[]).append(k); candidates.append(k)
    superseded={ref for item in candidates for ref in item.get("supersedes",[])}
    candidates=[item for item in candidates if item.get("id") not in superseded]
    if task is not None:
        candidates=[k for k in candidates if k.get("_task_id")==task or (terms and ranking({**k,"summary":k.get("_rank_words","")},terms)>0)]
    remaining={}
    for item in candidates: remaining.setdefault(item.get("key"),[]).append(item)
    conflicts=[key for key,items in remaining.items() if len({i.get("summary") for i in items})>1]
    if terms and task is None:
        candidates=[k for k in candidates if ranking({**k,"summary":k.get("_rank_words","")},terms)>0]
    for k in candidates: k.pop("_rank_words",None); k.pop("_task_id",None)
    candidates.sort(key=lambda k:(ranking(k,terms),k.get("id","")),reverse=True)
    active=[]
    if not task and include_active_tasks:
        active_candidates=[]
        for t in dict.fromkeys(e.get("task_id") for e in reversed(rows) if isinstance(e.get("task_id"),str)):
            e=latest_task(rows,t)
            if e and e.get("checkpoint",{}).get("status")=="in_progress":
                cp=e["checkpoint"]; text=" ".join((cp.get("goal",""),cp.get("next_step","")))
                score=len(norm(text)&terms)
                if terms and score==0: continue
                active_candidates.append((score,e.get("created_at",""),{"task_id":t,"goal":cp.get("goal","")[:120]}))
        active_candidates.sort(key=lambda item:(item[0],item[1]),reverse=True)
        active=[item[2] for item in active_candidates[:2]]
    e=latest_task(rows,task) if task else None
    result={"status":"DEGRADED" if errs or invalid else "OK","errors":errs[:10],"task_error":"revision_chain_invalid" if invalid else None,"knowledge":candidates[:5],"active_tasks":active,"conflicts":conflicts,"task_id":task,"checkpoint":e.get("checkpoint") if e else None,"revision":e.get("revision",0) if e else 0}
    if len(candidates)>5: result["omitted_count"]=len(candidates)-5
    return result
def export(root,base):
    rows,errs=records(base); curated,curated_err=curated_records(root); errs.extend(curated_err); chosen={}
    source_items=[k for e in rows for k in e.get("knowledge",[])] + curated
    for k in source_items:
        states=[source_state(root,a) for a in k.get("anchors",[])]
        if k.get("scope")!="repo" or any(s in ("source_changed","source_missing","worktree_only") for s in states): continue
        portable={a:v for a,v in k.items() if a not in {"provenance_state","current_assertion"}}
        portable["anchors"]=[{a:v for a,v in anc.items() if a in ("path","sha256","state")} for anc in portable.get("anchors",[])]
        chosen[portable.get("id")]=portable
    items=list(chosen.values())[-100:]; bykey={}
    superseded={ref for k in items for ref in k.get("supersedes",[])}
    items=[k for k in items if k.get("id") not in superseded]; bykey={}
    for k in items: bykey.setdefault(k.get("key"),[]).append(k)
    superseded={ref for k in items for ref in k.get("supersedes",[])}
    conflicts=[key for key,group in bykey.items() if len({k.get("summary") for k in group if k.get("id") not in superseded})>1]
    return {"status":"DEGRADED" if errs else "OK","knowledge":items,"conflicts":conflicts,"errors":errs[:10]}
def bound(out):
    omitted=0
    while len(compact(out).encode("utf-8"))+1>MAX_OUT:
        if isinstance(out.get("knowledge"),list) and out["knowledge"]:
            out["knowledge"].pop(); omitted+=1; out["omitted_count"]=omitted
        elif isinstance(out.get("recall"),dict) and out["recall"].get("knowledge"):
            out["recall"]["knowledge"].pop(); omitted+=1; out["omitted_count"]=omitted
        elif out.get("active_tasks"): out["active_tasks"].pop(); omitted+=1; out["omitted_count"]=omitted
        elif out.get("errors"): out["errors"].pop(); omitted+=1; out["omitted_count"]=omitted
        elif out.get("conflicts"): out["conflicts"].pop(); omitted+=1; out["omitted_count"]=omitted
        else: raise MemError("response cannot fit 8 KB")
    return compact(out)
if __name__=="__main__": raise SystemExit(main())
