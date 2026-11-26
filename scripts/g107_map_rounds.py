#!/usr/bin/env python3
"""Map the owner's audit-3886 round commits to the 120 Group107 registry IDs,
then verify each matched ID actually appears in origin/main source/tests."""
import json, re, subprocess

def sh(*args):
    return subprocess.run(args, capture_output=True, text=True).stdout

# 1. Parse audit-3886 round commit subjects from origin/main
log = sh("git", "log", "--format=%H%x09%s", "origin/main")
commits = []  # (sha, pr, round, [ids])
for line in log.splitlines():
    if "3886" not in line:
        continue
    sha, subj = line.split("\t", 1)
    m_pr = re.search(r"\(#(\d+)\)$", subj)
    m_rd = re.search(r"round (\d+)", subj)
    # extract ID tokens incl. ranges like EMRPRES-FE-001..004 and slashes 001/002/003
    ids = []
    for tok in re.findall(r"[A-Z]+-FE-\d+(?:\.\.\d+|/\d+)*", subj):
        if ".." in tok:
            base, rng = tok.split("..")
            pre = base.rsplit("-", 1)[0]
            for n in range(int(base.rsplit("-", 1)[1]), int(rng) + 1):
                ids.append(f"{pre}-{n:03d}")
        else:
            parts = tok.split("/")
            m_base = re.match(r"^(.*-FE-)(\d+)$", parts[0])
            base_pre, first_n = m_base.group(1), int(m_base.group(2))
            for part in parts:
                ids.append(parts[0] if part == parts[0] else f"{base_pre}{int(part):03d}")
    commits.append((sha[:9], m_pr.group(1) if m_pr else None, int(m_rd.group(1)) if m_rd else None, ids))

print(f"audit-3886 commits parsed: {len(commits)}")

# 2. Load the 120 Group107 UNVERIFIED entries
reg = json.load(open("docs/audit-registry/registry.json", encoding="utf-8"))
g107 = [e for e in reg["entries"] if e["status"] == "UNVERIFIED" and str(e.get("source", "")).startswith("#4063 Group107")]
want = {e["id"] for e in g107}
print(f"Group107 entries: {len(want)}")

# 3. Match every ID to its fix commit
id2fix = {}
for sha, pr, rd, ids in commits:
    for i in ids:
        id2fix.setdefault(i, (sha, pr, rd))
matched = {i: id2fix[i] for i in want if i in id2fix}
unmatched = sorted(want - set(id2fix))
print(f"matched: {len(matched)} | unmatched: {unmatched}")

# 4. Evidence grep: ID present in origin/main frontend/backend tests
result = {}
for i, (sha, pr, rd) in sorted(matched.items()):
    src = sh("git", "grep", "-l", "-I", i, "origin/main", "--", "frontend/src", ":!frontend/src/types/generated")
    tst = sh("git", "grep", "-l", "-I", i, "origin/main", "--", "frontend/src/components", "frontend/src/pages", "frontend/src/utils", "frontend/src/hooks", "backend/tests")
    n_src = len([x for x in src.splitlines() if x])
    files = sorted(set(x.split(":", 1)[1] for x in src.splitlines() if x))[:3]
    result[i] = {"fix_sha": sha, "fix_pr": pr, "round": rd, "src_hits": n_src, "sample_files": files}
    flag = "OK " if n_src > 0 else "NO-SOURCE-HIT"
    print(f"{flag} {i:22s} round{rd:>3} #{pr} {sha} src_files={n_src} e.g. {files[:2]}")

json.dump(result, open("/tmp/g107_mapping.json", "w"), indent=1)
print("\nsaved /tmp/g107_mapping.json; no-source-hit IDs:", [i for i, v in result.items() if v["src_hits"] == 0])
