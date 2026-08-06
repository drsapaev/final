#!/usr/bin/env python3
"""
Parse `ps -eo pid,ppid,comm,args` output to identify vitest processes.

Reads /tmp/proc-tree.txt (saved by the CI workflow) and emits shell
assignments to /tmp/vitest-pids.sh:

    export MAIN_VITEST_PID=<pid or empty>
    export WORKER_PIDS='<space-separated pids or empty>'
    echo 'Main vitest PID: <pid or (not found)>'
    echo 'Worker PIDs: <pids or (none)>'

Identification logic (per maintainer feedback — NOT pgrep):
  1. Filter to comm == 'node' (standard procps-ng on GitHub Actions Ubuntu)
  2. Exclude any process with 'esbuild' in args
  3. Main vitest = node process with 'vitest' in args, whose PARENT is
     NOT a node process (parent is sh / npm / etc.)
  4. Workers = node processes whose parent PID == main vitest PID

This file lives in the repo (scripts/ci/) so the workflow can invoke it
directly, avoiding bash heredoc quoting issues with embedded Python.
"""

import sys


def main():
    with open('/tmp/proc-tree.txt') as f:
        lines = f.readlines()

    procs = {}
    for line in lines[1:]:  # skip header
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        comm = parts[2]
        args = parts[3]
        procs[pid] = {'ppid': ppid, 'comm': comm, 'args': args}

    # Node processes, excluding esbuild
    node_procs = {}
    for pid, info in procs.items():
        if info['comm'] != 'node':
            continue
        if 'esbuild' in info['args']:
            continue
        node_procs[pid] = info

    # Main vitest: node process with 'vitest' in args,
    # whose parent is NOT a node process (parent is sh/npm)
    main_pid = None
    for pid, info in node_procs.items():
        if 'vitest' not in info['args']:
            continue
        parent = procs.get(info['ppid'])
        if parent is None or parent['comm'] != 'node':
            main_pid = pid
            break

    # Workers: node processes whose parent is main_pid
    workers = []
    if main_pid:
        for pid, info in node_procs.items():
            if info['ppid'] == main_pid and pid != main_pid:
                workers.append(pid)

    workers_str = ' '.join(map(str, sorted(workers)))
    main_str = str(main_pid) if main_pid else ''

    # Emit shell assignments
    print(f"export MAIN_VITEST_PID={main_str}")
    print(f"export WORKER_PIDS='{workers_str}'")
    main_label = main_str if main_str else '(not found)'
    workers_label = workers_str if workers_str else '(none)'
    print(f"echo 'Main vitest PID: {main_label}'")
    print(f"echo 'Worker PIDs: {workers_label}'")


if __name__ == '__main__':
    main()
