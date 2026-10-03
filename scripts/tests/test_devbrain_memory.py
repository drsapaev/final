"""Isolated synthetic-git acceptance tests for local memory."""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"devbrain_memory.py"
LAUNCHER=SCRIPT.with_name("run_devbrain_memory.ps1")
KN={"schema_version":1,"id":"k1","key":"queue-owner","kind":"fact","topic":"queue","summary":"Queue ownership stays backend controlled","tags":["queue"],"scope":"repo","source_type":"source","evidence_summary":"Verified source contract","anchors":["source.py"],"supersedes":[]}
CP={"goal":"Inspect queue ownership","status":"in_progress","allowed_paths":["src"],"denied_paths":["secrets"],"completed":[],"next_step":"Read service","blockers":[],"artifacts":[],"validation_reported":False}

class MemoryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.base=Path(self.tmp.name); self.root=self.base/"repo"; self.root.mkdir()
  subprocess.run(["git","init","-q",str(self.root)],check=True); subprocess.run(["git","-C",str(self.root),"config","user.email","test@example.invalid"],check=True); subprocess.run(["git","-C",str(self.root),"config","user.name","Test"],check=True)
  (self.root/"source.py").write_text("x = 1\n"); subprocess.run(["git","-C",str(self.root),"add","source.py"],check=True); subprocess.run(["git","-C",str(self.root),"commit","-qm","init"],check=True)
 def tearDown(self): self.tmp.cleanup()
 def runmem(self,action,obj=None,cwd=None,expected=0,extra=()):
  args=[sys.executable,str(SCRIPT),action,*extra]; input_data=json.dumps(obj or {}).encode()
  if action=="begin" and obj is not None:
   payload=self.root/".begin-input.json"; payload.write_bytes(input_data); args.extend(("--input-file",str(payload))); input_data=None
  p=subprocess.run(args,cwd=cwd or self.root,input=input_data,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  self.assertEqual(p.returncode,expected,p.stderr.decode()); return json.loads(p.stdout or p.stderr)
 def capture(self,task="alpha",rev=0,idem=None,knowledge=None,checkpoint=None):
  return self.runmem("capture",{"task_id":task,"expected_revision":rev,"checkpoint":checkpoint or CP,"knowledge":knowledge or [KN],"idempotency_key":idem})
 def test_begin_creates_id_and_checkpoint_then_new_process_recalls(self):
  b=self.runmem("begin",{"goal":"Check a contract"}); self.assertTrue(b["task_id"]); self.assertEqual(b["revision"],1)
  r=self.runmem("recall",cwd=self.root,extra=("--task-id",b["task_id"])); self.assertEqual(r["checkpoint"]["goal"],"Check a contract")
  self.capture(b["task_id"],rev=1,checkpoint=CP)
  r=self.runmem("recall",extra=("--task-id",b["task_id"])); self.assertEqual(r["checkpoint"]["completed"],CP["completed"]); self.assertEqual(r["checkpoint"]["next_step"],CP["next_step"]); self.assertEqual(r["checkpoint"]["validation_reported"],CP["validation_reported"])
 def test_revision_cas_noop_and_key_mismatch(self):
  self.assertEqual(self.capture(idem="one")["result"],"OK")
  self.assertEqual(self.capture(idem="one")["result"],"NOOP")
  self.capture(rev=1,checkpoint=dict(CP,next_step="Later"),idem="two")
  (self.root/"source.py").unlink()
  repeated=self.capture(rev=0,idem="one"); self.assertEqual(repeated["result"],"NOOP"); self.assertEqual(repeated["revision"],2); self.assertEqual(repeated["operation_revision"],1)
  changed=dict(KN,summary="Different content")
  conflict=self.capture(rev=0); self.assertEqual(conflict["result"],"CONFLICT"); self.assertEqual(conflict["current_revision"],2)
  p=subprocess.run([sys.executable,str(SCRIPT),"capture"],cwd=self.root,input=json.dumps({"task_id":"alpha","expected_revision":0,"checkpoint":CP,"knowledge":[changed],"idempotency_key":"one"}).encode(),capture_output=True)
  self.assertEqual(p.returncode,2); self.assertNotIn(b"Different content",p.stderr)
 def test_begin_idempotency_reuses_task_without_rewinding_checkpoint(self):
  first=self.runmem("begin",{"goal":"Start this task","idempotency_key":"begin-once"})
  self.assertEqual(first["result"],"OK")
  self.capture(first["task_id"],rev=1,checkpoint=dict(CP,next_step="Continue from saved state"))
  repeated=self.runmem("begin",{"goal":"Start this task","idempotency_key":"begin-once"})
  self.assertEqual(repeated["result"],"NOOP"); self.assertEqual(repeated["task_id"],first["task_id"])
  self.assertEqual(repeated["revision"],2); self.assertEqual(repeated["checkpoint"]["next_step"],"Continue from saved state")
  p=self.runmem("begin",{"goal":"Different request","idempotency_key":"begin-once"},expected=2)
  self.assertEqual(p["error"],"idempotency key content mismatch")
 def test_task_isolation_linked_worktrees_and_portable_export(self):
  self.capture("one",checkpoint=dict(CP,goal="Task one")); self.capture("two",checkpoint=dict(CP,goal="Task two"))
  linked=self.base/"linked"; linked2=self.base/"linked2"
  subprocess.run(["git","-C",str(self.root),"worktree","add","-qb","branch1",str(linked)],check=True)
  subprocess.run(["git","-C",str(self.root),"worktree","add","-qb","branch2",str(linked2)],check=True)
  self.assertEqual(self.runmem("recall",cwd=linked,extra=("--task-id","one"))["checkpoint"]["goal"],"Task one")
  self.assertEqual(self.runmem("recall",cwd=linked2,extra=("--task-id","two"))["checkpoint"]["goal"],"Task two")
  ex=self.runmem("export"); text=json.dumps(ex); self.assertNotIn(str(self.root),text); self.assertNotIn("task_id",text); self.assertNotIn("event_id",text)
 def test_incomplete_writes_leave_previous_checkpoint_readable(self):
  self.capture("recover",checkpoint=dict(CP,next_step="Last durable point"))
  common=subprocess.check_output(["git","-C",str(self.root),"rev-parse","--path-format=absolute","--git-common-dir"],text=True).strip()
  store=Path(common)/"devbrain-memory"/"v1"; (store/".lock").write_bytes(b"")
  self.capture("after-interrupted-lock")
  (store/"records"/".tmp-interrupted").write_text('{"partial":',encoding="utf-8")
  recovered=self.runmem("recall",extra=("--task-id","recover"))
  self.assertEqual(recovered["checkpoint"]["next_step"],"Last durable point"); self.assertEqual(recovered["status"],"OK")
  self.assertEqual((store/".lock").read_bytes(),b"0")
 def test_anchor_safety_and_provenance(self):
  self.capture("anchored")
  (self.root/"source.py").write_text("changed\n")
  r=self.runmem("recall",extra=("--query","queue")); self.assertEqual(r["knowledge"][0]["provenance_state"],"source_changed"); self.assertNotIn("summary",r["knowledge"][0]); self.assertFalse(r["knowledge"][0]["current_assertion"])
  self.assertNotIn("k1",[k["id"] for k in self.runmem("export")["knowledge"]])
  for bad in ("../outside","/tmp/private"):
   k=dict(KN,anchors=[bad]); p=subprocess.run([sys.executable,str(SCRIPT),"capture"],cwd=self.root,input=json.dumps({"task_id":"bad","expected_revision":0,"checkpoint":CP,"knowledge":[k]}).encode(),capture_output=True); self.assertEqual(p.returncode,2)
  outside=self.base/"outside.txt"; outside.write_text("must not read")
  link=self.root/"escape.txt"
  try: link.symlink_to(outside)
  except (OSError,NotImplementedError): pass
  else:
   k=dict(KN,anchors=["escape.txt"]); p=subprocess.run([sys.executable,str(SCRIPT),"capture"],cwd=self.root,input=json.dumps({"task_id":"symlink","expected_revision":0,"checkpoint":CP,"knowledge":[k]}).encode(),capture_output=True); self.assertEqual(p.returncode,2); self.assertNotIn(b"must not read",p.stderr)
  (self.root/".env").write_text("secret")
  self.assertEqual(self.runmem("capture",{"task_id":"bad","expected_revision":0,"checkpoint":CP,"knowledge":[dict(KN,anchors=[".env"] )]},expected=2)["error"],"anchor path rejected")
  nested=self.root/".env.local"; nested.mkdir(); (nested/"config.py").write_text("placeholder")
  self.assertEqual(self.runmem("capture",{"task_id":"bad-dir","expected_revision":0,"checkpoint":CP,"knowledge":[dict(KN,anchors=[".env.local/config.py"])]},expected=2)["error"],"anchor path rejected")
 def test_sensitive_payload_not_echoed_and_corrupt_degraded(self):
  phone=self.root/"phone-input.json"; phone.write_bytes(b'{"goal":"phone +998901234567"}')
  p=subprocess.run([sys.executable,str(SCRIPT),"begin","--input-file",str(phone)],cwd=self.root,capture_output=True)
  self.assertEqual(p.returncode,2); self.assertNotIn(b"+998901234567",p.stderr)
  email=self.root/"email-input.json"; email.write_bytes(b'{"goal":"contact a@example.com"}')
  p=subprocess.run([sys.executable,str(SCRIPT),"begin","--input-file",str(email)],cwd=self.root,capture_output=True)
  self.assertEqual(p.returncode,2); self.assertNotIn(b"a@example.com",p.stderr)
  self.runmem("status")
  common=subprocess.check_output(["git","-C",str(self.root),"rev-parse","--path-format=absolute","--git-common-dir"],text=True).strip()
  rec=Path(common)/"devbrain-memory"/"v1"/"records"; rec.mkdir(parents=True,exist_ok=True); (rec/"truncated.json").write_text("{")
  self.assertEqual(self.runmem("status")["status"],"DEGRADED")
  malformed={"event_id":"badshape","task_id":"badshape","revision":1,"parent_event_id":None,"created_at":"now","worktree":str(self.root),"branch":"main","head":"test","checkpoint":"not-an-object","knowledge":[],"idempotency_key":None,"request_digest":None}
  (rec/"badshape.json").write_text(json.dumps(malformed),encoding="utf-8")
  self.assertEqual(self.runmem("status")["status"],"DEGRADED")
 def test_dirty_and_missing_sources_are_not_current_assertions(self):
  (self.root/"source.py").write_text("dirty\n")
  self.capture("dirty")
  r=self.runmem("recall",extra=("--task-id","dirty")); self.assertEqual(r["knowledge"][0]["provenance_state"],"worktree_only"); self.assertFalse(r["knowledge"][0]["current_assertion"]); self.assertEqual(r["knowledge"][0]["scope"],"worktree")
  linked=self.base/"dirty-linked"; subprocess.run(["git","-C",str(self.root),"worktree","add","-qb","dirty-branch",str(linked)],check=True)
  shared=self.runmem("recall",cwd=linked,extra=("--task-id","dirty")); self.assertEqual(shared["knowledge"][0]["provenance_state"],"worktree_only"); self.assertFalse(shared["knowledge"][0]["current_assertion"])
  self.capture("missing",rev=0)
  (self.root/"source.py").unlink()
  r=self.runmem("recall",extra=("--task-id","missing")); self.assertEqual(r["knowledge"][0]["provenance_state"],"source_missing"); self.assertNotIn("summary",r["knowledge"][0])
 def test_duplicate_key_conflict_and_supersedes(self):
  self.capture("knowledge",knowledge=[KN])
  changed=dict(KN,id="k2",summary="Different summary",supersedes=[])
  self.capture("knowledge",rev=1,knowledge=[changed])
  self.assertIn("queue-owner",self.runmem("recall",extra=("--query","queue"))["conflicts"])
  replacement=dict(KN,id="k3",summary="Resolved summary",supersedes=["k1","k2"])
  self.capture("knowledge",rev=2,knowledge=[replacement])
  self.assertNotIn("queue-owner",self.runmem("recall",extra=("--query","queue"))["conflicts"])
  wrong_key=dict(KN,id="k4",key="unrelated",supersedes=["k3"])
  invalid=self.runmem("capture",{"task_id":"knowledge","expected_revision":3,"checkpoint":CP,"knowledge":[wrong_key]},expected=2)
  self.assertEqual(invalid["error"],"supersedes key mismatch")
 def test_source_facts_need_anchors_but_user_decisions_do_not(self):
  invalid=dict(KN,anchors=[])
  result=self.runmem("capture",{"task_id":"unanchored","expected_revision":0,"checkpoint":CP,"knowledge":[invalid]},expected=2)
  self.assertEqual(result["error"],"source-backed knowledge requires an anchor")
  decision=dict(KN,id="user-decision",key="memory-boundary",kind="decision",source_type="user_evidence",topic="memory",summary="Keep local memory advisory",evidence_summary="Explicit user decision",scope="repo",anchors=[])
  self.assertEqual(self.capture("decision",knowledge=[decision])["result"],"OK")
  recalled=self.runmem("recall",extra=("--task-id","decision"))["knowledge"][0]
  self.assertFalse(recalled["current_assertion"]); self.assertEqual(recalled["provenance_state"],"sources_match")
 def test_schema_values_and_revision_parent_integrity(self):
  invalid=dict(KN,scope="anywhere")
  p=subprocess.run([sys.executable,str(SCRIPT),"capture"],cwd=self.root,input=json.dumps({"task_id":"bad-scope","expected_revision":0,"checkpoint":CP,"knowledge":[invalid]}).encode(),capture_output=True)
  self.assertEqual(p.returncode,2)
  self.capture("chain"); self.capture("chain",rev=1,checkpoint=dict(CP,next_step="second"))
  common=subprocess.check_output(["git","-C",str(self.root),"rev-parse","--path-format=absolute","--git-common-dir"],text=True).strip()
  rec=Path(common)/"devbrain-memory"/"v1"/"records"
  for f in rec.glob("*.json"):
   e=json.loads(f.read_text())
   if e.get("task_id")=="chain" and e.get("revision")==2: e["parent_event_id"]="wrong-parent"; f.write_text(json.dumps(e))
  self.assertEqual(self.runmem("status")["status"],"DEGRADED")
  r=self.runmem("recall",extra=("--task-id","chain")); self.assertEqual(r["status"],"DEGRADED"); self.assertEqual(r["task_error"],"revision_chain_invalid"); self.assertIsNone(r["checkpoint"])
 def test_ignored_anchors_and_task_scoped_recall(self):
  (self.root/".gitignore").write_text("ignored.py\n"); subprocess.run(["git","-C",str(self.root),"add",".gitignore"],check=True); subprocess.run(["git","-C",str(self.root),"commit","-qm","ignore fixture"],check=True)
  (self.root/"ignored.py").write_text("private local source\n")
  ignored=dict(KN,id="ignored",anchors=["ignored.py"]); self.capture("ignored-task",knowledge=[ignored])
  local=self.runmem("recall",extra=("--task-id","ignored-task")); self.assertEqual(local["knowledge"][0]["provenance_state"],"worktree_only")
  linked=self.base/"ignored-linked"; subprocess.run(["git","-C",str(self.root),"worktree","add","-qb","ignored-branch",str(linked)],check=True)
  cross=self.runmem("recall",cwd=linked,extra=("--task-id","ignored-task")); self.assertEqual(cross["knowledge"][0]["provenance_state"],"source_missing"); self.assertNotIn("summary",cross["knowledge"][0])
  task_fact=dict(KN,id="task-fact",key="registrar-private-note",scope="task",topic="registrar",summary="Task-only persistence note")
  self.capture("registrar-task",knowledge=[task_fact],checkpoint=dict(CP,goal="Registrar partial payment persistence"))
  global_recall=self.runmem("recall",extra=("--query","registrar persistence"))
  self.assertNotIn("task-fact",[item["id"] for item in global_recall["knowledge"]]); self.assertEqual(global_recall["active_tasks"][0]["task_id"],"registrar-task")
  exact=self.runmem("recall",extra=("--task-id","registrar-task")); self.assertEqual(exact["knowledge"][0]["id"],"task-fact"); self.assertFalse(exact["knowledge"][0]["current_assertion"])
  worktree_fact=dict(KN,id="worktree-fact",key="local-observation",scope="worktree")
  self.capture("worktree-task",knowledge=[worktree_fact])
  local=self.runmem("recall",cwd=self.root,extra=("--task-id","worktree-task")); self.assertEqual(local["knowledge"][0]["provenance_state"],"sources_match"); self.assertFalse(local["knowledge"][0]["current_assertion"])
  remote=self.runmem("recall",cwd=linked,extra=("--task-id","worktree-task")); self.assertEqual(remote["knowledge"][0]["provenance_state"],"worktree_only")
 def test_begin_response_omits_nested_knowledge_when_needed(self):
  long=dict(KN,summary="huge "+"x"*1100,evidence_summary="e"*1000,anchors=["source.py"])
  for i in range(5): self.capture(f"large{i}",knowledge=[dict(long,id=f"large{i}",key=f"huge-key-{i}")])
  result=self.runmem("begin",{},extra=("--query","huge")); encoded=json.dumps(result,separators=(",",":")).encode()
  self.assertLessEqual(len(encoded),8192); self.assertGreater(result.get("omitted_count",0),0)
  stdout=subprocess.run([sys.executable,str(SCRIPT),"recall","--query","huge"],cwd=self.root,capture_output=True,check=True).stdout
  self.assertLessEqual(len(stdout),8192)
 def test_unicode_topics_rank_knowledge(self):
  russian=dict(KN,id="ru",key="\u043e\u0447\u0435\u0440\u0435\u0434\u044c-\u0432\u0440\u0430\u0447\u0430",topic="\u043e\u0447\u0435\u0440\u0435\u0434\u044c",summary="\u0412\u043b\u0430\u0434\u0435\u043b\u0435\u0446 \u043e\u0447\u0435\u0440\u0435\u0434\u0438 \u043e\u043f\u0440\u0435\u0434\u0435\u043b\u044f\u0435\u0442\u0441\u044f \u0441\u0435\u0440\u0432\u0435\u0440\u043e\u043c",tags=["\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0442\u0443\u0440\u0430"],anchors=["source.py"])
  self.capture("russian",knowledge=[russian])
  result=self.runmem("recall",extra=("--query","\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0442\u0443\u0440\u0430"))
  self.assertEqual(result["knowledge"][0]["id"],"ru")
 def test_concurrent_writes_and_many_records_bounded(self):
  ps=[]
  for i in range(3):
   payload={"task_id":f"t{i}","expected_revision":0,"checkpoint":CP,"knowledge":[dict(KN,id=f"k{i}",key=f"key{i}")]}
   ps.append((subprocess.Popen([sys.executable,str(SCRIPT),"capture"],cwd=self.root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE),payload))
  for proc,payload in ps: proc.stdin.write(json.dumps(payload).encode()); proc.stdin.close(); proc.stdin=None
  for proc,_ in ps:
   stdout,stderr=proc.communicate(timeout=10); self.assertEqual(proc.returncode,0,stderr.decode()); self.assertEqual(json.loads(stdout)["result"],"OK")
  # Competing writes against the same revision must yield one winner.
  race=[]
  for i in range(2):
   payload={"task_id":"race","expected_revision":0,"checkpoint":CP,"knowledge":[dict(KN,id=f"race{i}")]}
   race.append((subprocess.Popen([sys.executable,str(SCRIPT),"capture"],cwd=self.root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE),payload))
  for proc,payload in race: proc.stdin.write(json.dumps(payload).encode()); proc.stdin.close(); proc.stdin=None
  outcomes=[]
  for proc,_ in race:
   stdout,stderr=proc.communicate(timeout=10); self.assertEqual(proc.returncode,0,stderr.decode()); outcomes.append(json.loads(stdout)["result"])
  self.assertCountEqual(outcomes,["OK","CONFLICT"])
  # Recall output remains bounded even after many independent events.
  common=subprocess.check_output(["git","-C",str(self.root),"rev-parse","--path-format=absolute","--git-common-dir"],text=True).strip()
  records=Path(common)/"devbrain-memory"/"v1"/"records"
  for i in range(1000):
   item=dict(KN,id=f"bulk{i}",kind="decision",source_type="user_evidence",anchors=[])
   e={"event_id":f"bulk-{i}","task_id":f"bulk{i}","revision":1,"parent_event_id":None,"created_at":"now","worktree":str(self.root),"branch":"synthetic","head":"synthetic","checkpoint":CP,"knowledge":[item],"idempotency_key":None,"request_digest":None}
   (records/f"bulk-{i}.json").write_text(json.dumps(e),encoding="utf-8")
  out=self.runmem("recall",extra=("--query","queue")); self.assertLessEqual(len(json.dumps(out,separators=(",",":")).encode()),8192)
 def test_launcher_interface(self):
  if os.name!="nt": self.skipTest("PowerShell wrapper is Windows-only")
  self.capture("seed")
  p=subprocess.run(["pwsh","-NoProfile","-File",str(LAUNCHER),"-Action","begin","-Query","not-a-match","-Topics","queue"],cwd=self.root,input="{}",text=True,capture_output=True)
  self.assertEqual(p.returncode,0,p.stderr); result=json.loads(p.stdout); self.assertEqual(result["checkpoint"]["goal"],"not-a-match"); self.assertEqual(result["recall"]["knowledge"][0]["key"],"queue-owner")
  no_stdin=subprocess.run(["pwsh","-NoProfile","-File",str(LAUNCHER),"-Action","begin","-Query","no stdin needed"],cwd=self.root,text=True,capture_output=True,timeout=10)
  self.assertEqual(no_stdin.returncode,0,no_stdin.stderr); self.assertEqual(json.loads(no_stdin.stdout)["checkpoint"]["goal"],"no stdin needed")

if __name__=="__main__": unittest.main()
