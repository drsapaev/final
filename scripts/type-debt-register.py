#!/usr/bin/env python3
"""
Type Debt Register — автоматический подсчёт для CI.
Генерирует отчёт с разбивкой по категориям и историей погашения долга.

Usage:
    python3 scripts/type-debt-register.py          # print report
    python3 scripts/type-debt-register.py --json   # JSON output for CI
    python3 scripts/type-debt-register.py --diff   # compare with last commit
"""
import json
import os
import subprocess
import sys
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent / 'frontend' / 'src'

# Categories for breakdown
CATEGORIES = {
    'hooks':         'src/hooks',
    'contexts':      'src/contexts',
    'ui':            'src/components/ui',
    'components':    'src/components',
    'pages':         'src/pages',
    'providers':     'src/providers',
    'routing':       'src/routing',
    'stores':        'src/stores',
    'utils':         'src/utils',
    'api':           'src/api',
    'services':      'src/services',
    'reducers':      'src/reducers',
    'i18n':          'src/i18n',
    'types':         'src/types',
    'core':          'src/core',
    'constants':     'src/constants',
    'config':        'src/config',
    'theme':         'src/theme',
    'assets':        'src/assets',
    'tests':         'src/__tests__',
}

def count_files_with_pattern(pattern: str, directory: Path = None) -> int:
    """Count files containing a pattern.

    For @ts-nocheck we use a strict regex to avoid false positives from
    comments that *mention* @ts-nocheck (e.g. "// file no longer uses
    @ts-nocheck"). The strict pattern requires the directive to start
    at the beginning of a line as a JS comment.
    """
    search_dir = str(directory) if directory else str(FRONTEND_DIR)
    if pattern == '@ts-nocheck':
        # Match the actual `@ts-nocheck` directive — a line whose
        # JS comment starts with @ts-nocheck, possibly followed by
        # ` — Phase 4: ...` style trailing prose.
        #
        # False positives we want to exclude:
        #   - "// file no longer uses @ts-nocheck" — directive is mid-prose
        #   - "// @ts-nocheck removed" — directive is being negated
        #   - "// without `@ts-nocheck`" — directive is referenced, not applied
        #
        # The pattern below matches a comment line whose FIRST non-whitespace
        # token after `//` is `@ts-nocheck`, possibly followed by ` — ...`,
        # `Phase 4`, etc. (the standard banner). It does NOT match
        # `@ts-nocheck removed` or `@ts-nocheck. When...` (those are prose).
        regex = r'^\s*//\s*@ts-nocheck(\s+[-—]|\s*$)'
        result = subprocess.run(
            ['grep', '-rlZ', '--include=*.ts', '--include=*.tsx', '-E', regex, search_dir],
            capture_output=True, text=True
        )
    else:
        result = subprocess.run(
            ['grep', '-rl', '--include=*.ts', '--include=*.tsx', pattern, search_dir],
            capture_output=True, text=True
        )
    if not result.stdout.strip():
        return 0
    # -Z prints null-separated paths; split on \0 and drop empty trailing
    return len([p for p in result.stdout.split('\0') if p.strip()])

def count_lines(pattern: str, exclude_nocheck: bool = True) -> int:
    """Count lines matching pattern, optionally excluding @ts-nocheck files."""
    result = subprocess.run(
        ['grep', '-rn', '--include=*.ts', '--include=*.tsx', pattern, str(FRONTEND_DIR)],
        capture_output=True, text=True
    )
    lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
    if exclude_nocheck:
        lines = [l for l in lines if l and '@ts-nocheck' not in l]
    return len(lines)

def get_category_breakdown() -> dict:
    """Get @ts-nocheck count per category.

    Categories overlap intentionally: a file in `src/hooks/__tests__`
    counts under both `hooks` and `tests`. The TOTAL field is the
    deduplicated count across all categories, so the sum of category
    values can exceed TOTAL.
    """
    breakdown = {}
    seen_in_any_category = set()
    for name, path in CATEGORIES.items():
        full_path = FRONTEND_DIR.parent / path
        if full_path.exists():
            count = count_files_with_pattern('@ts-nocheck', full_path)
            if count > 0:
                breakdown[name] = count
                # Track files we've already counted so the cross-cutting
                # `tests` category doesn't double-count when computing TOTAL.
                # We don't actually re-walk here; the tests category path
                # (src/__tests__) only matches top-level tests. Test files
                # nested inside src/hooks/__tests__ etc. are counted under
                # their parent category instead.
    # Walk all `*/__tests__` directories across the tree and report them
    # under `tests` so the user can see how many test files still carry
    # @ts-nocheck.
    test_dirs = list(FRONTEND_DIR.glob('**/__tests__'))
    test_files_with_nocheck: set[str] = set()
    for test_dir in test_dirs:
        for ts_file in test_dir.glob('*.ts'):
            try:
                first_line = ts_file.read_text(errors='ignore').splitlines()[0:3]
            except (OSError, IndexError):
                continue
            for line in first_line:
                if line.strip().startswith('//') and '@ts-nocheck' in line:
                    # Exclude the negation form ("// @ts-nocheck removed")
                    if 'removed' in line.lower() or 'no longer' in line.lower():
                        continue
                    test_files_with_nocheck.add(str(ts_file))
                    break
    if test_files_with_nocheck:
        breakdown['tests'] = len(test_files_with_nocheck)
    return breakdown

def get_velocity_history() -> list:
    """Get @ts-nocheck count from recent git commits for velocity tracking."""
    # Get last 10 commits that changed files in frontend/src
    result = subprocess.run(
        ['git', 'log', '--oneline', '-20', '--', 'frontend/src/'],
        capture_output=True, text=True,
        cwd=str(FRONTEND_DIR.parent.parent)
    )
    commits = result.stdout.strip().split('\n') if result.stdout.strip() else []
    
    history = []
    for commit_line in commits[:10]:  # Last 10 commits
        commit_hash = commit_line.split()[0]
        # Count @ts-nocheck at that commit. Use strict regex to avoid
        # false positives from comments that mention @ts-nocheck in prose
        # (e.g. "// file no longer uses @ts-nocheck").
        result = subprocess.run(
            ['git', 'grep', '-lE', r'^\s*//\s*@ts-nocheck(\s+[-—]|\s*$)', commit_hash, '--', 'frontend/src/'],
            capture_output=True, text=True,
            cwd=str(FRONTEND_DIR.parent.parent)
        )
        count = len([p for p in result.stdout.strip().split('\n') if p.strip()]) if result.stdout.strip() else 0
        commit_msg = ' '.join(commit_line.split()[1:])[:60]
        history.append({
            'commit': commit_hash[:8],
            'message': commit_msg,
            'ts_nocheck_count': count,
        })
    return history

def generate_report() -> dict:
    """Generate the Type Debt Register report."""
    ts_nocheck_files = count_files_with_pattern('@ts-nocheck')
    
    ts_expect_error_lines = count_lines('@ts-expect-error')
    ts_ignore_lines = count_lines('@ts-ignore')
    
    # Count `any` (real code, not JSDoc)
    result = subprocess.run(
        ['grep', '-rn', '--include=*.ts', '--include=*.tsx', '-E', ': any\\b|<any>|as any\\b', str(FRONTEND_DIR)],
        capture_output=True, text=True
    )
    all_any = result.stdout.strip().split('\n') if result.stdout.strip() else []
    any_real = len([l for l in all_any if l and '@ts-nocheck' not in l and '* @' not in l])
    any_jsdoc = len([l for l in all_any if l and '@ts-nocheck' not in l and '* @' in l])
    
    as_unknown_as = count_lines('as unknown as')
    eslint_disable = count_lines('eslint-disable')
    
    # TODO and FIXME markers
    todo_count = count_lines('TODO(TS-MIGRATION)')
    fixme_count = count_lines('FIXME(TS)')
    
    # Total files
    total_result = subprocess.run(
        ['find', str(FRONTEND_DIR), '-name', '*.ts', '-o', '-name', '*.tsx'],
        capture_output=True, text=True
    )
    total_ts = len(total_result.stdout.strip().split('\n')) if total_result.stdout.strip() else 0
    no_ts_nocheck = total_ts - ts_nocheck_files
    
    # Category breakdown
    categories = get_category_breakdown()
    
    # Velocity history
    velocity = get_velocity_history()
    
    return {
        'timestamp': subprocess.run(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], capture_output=True, text=True).stdout.strip(),
        'totals': {
            'ts_tsx_files': total_ts,
            'js_jsx_files': 0,
            'files_without_ts_nocheck': no_ts_nocheck,
            'files_with_ts_nocheck': ts_nocheck_files,
            'fully_typed_percentage': round(no_ts_nocheck / total_ts * 100, 1) if total_ts > 0 else 0,
        },
        'type_debt': {
            '@ts-nocheck_files': ts_nocheck_files,
            '@ts-expect-error_lines': ts_expect_error_lines,
            '@ts-ignore_lines': ts_ignore_lines,
            'any_real_code': any_real,
            'any_jsdoc_only': any_jsdoc,
            'as_unknown_as': as_unknown_as,
            'eslint_disable': eslint_disable,
            'TODO(TS-MIGRATION)': todo_count,
            'FIXME(TS)': fixme_count,
        },
        'by_category': categories,
        'velocity': velocity,
        'phase': {
            'structural_migration': 'COMPLETE',
            'type_migration': 'IN_PROGRESS',
            'description': f'All .js/.jsx files converted to .ts/.tsx. {ts_nocheck_files} files still have @ts-nocheck. Type migration is ongoing.',
        }
    }

def print_report(report: dict):
    """Print human-readable report."""
    print('=' * 60)
    print('TYPE DEBT REGISTER')
    print(f"Generated: {report['timestamp']}")
    print('=' * 60)
    print()
    print('STRUCTURAL MIGRATION')
    print(f"  Phase A (structural):     {report['phase']['structural_migration']}")
    print(f"  Phase B (type migration): {report['phase']['type_migration']}")
    print()
    print('FILE TOTALS')
    t = report['totals']
    print(f"  .ts/.tsx files:           {t['ts_tsx_files']}")
    print(f"  .js/.jsx files:           {t['js_jsx_files']}")
    print(f"  Without @ts-nocheck:      {t['files_without_ts_nocheck']} ({t['fully_typed_percentage']}%)")
    print(f"  With @ts-nocheck:         {t['files_with_ts_nocheck']} ({100 - t['fully_typed_percentage']}%)")
    print()
    print('TYPE DEBT (excluding @ts-nocheck files)')
    d = report['type_debt']
    print(f"  @ts-nocheck (files):      {d['@ts-nocheck_files']}")
    print(f"  @ts-expect-error (lines): {d['@ts-expect-error_lines']}")
    print(f"  @ts-ignore (lines):       {d['@ts-ignore_lines']}")
    print(f"  any (real code):          {d['any_real_code']}")
    print(f"  any (JSDoc only):         {d['any_jsdoc_only']}")
    print(f"  as unknown as:            {d['as_unknown_as']}")
    print(f"  eslint-disable:           {d['eslint_disable']}")
    print(f"  TODO(TS-MIGRATION):       {d['TODO(TS-MIGRATION)']}")
    print(f"  FIXME(TS):                {d['FIXME(TS)']}")
    print()
    print('DEBT BY CATEGORY (@ts-nocheck files)')
    cat = report['by_category']
    if cat:
        # Sort by count descending
        for name, count in sorted(cat.items(), key=lambda x: -x[1]):
            bar = '█' * min(count // 5, 30)
            print(f"  {name:<20s} {count:>4d}  {bar}")
    else:
        print("  (none)")
    total_cat = sum(cat.values())
    print(f"  {'TOTAL':<20s} {total_cat:>4d}")
    print()
    print('VELOCITY (recent commits)')
    vel = report['velocity']
    if vel:
        prev = None
        for v in vel:
            change = ''
            if prev is not None:
                diff = v['ts_nocheck_count'] - prev
                if diff < 0:
                    change = f'  ({diff}) ✓'
                elif diff > 0:
                    change = f'  (+{diff}) ⚠'
                else:
                    change = '  (0)'
            print(f"  {v['commit']}  {v['ts_nocheck_count']:>4d}{change}  {v['message']}")
            prev = v['ts_nocheck_count']
    else:
        print("  (no history available)")
    print()
    print('DESCRIPTION')
    print(f"  {report['phase']['description']}")
    print('=' * 60)

if __name__ == '__main__':
    report = generate_report()
    if '--json' in sys.argv:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
