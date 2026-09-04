#!/usr/bin/env python3
"""
Parse mutation score from mutmut 3.x output (mutmut run | tee mutmut-output.txt).

mutmut 3.7 summary line (mutmut/__main__.py, print_stats):
    <checked>/<total>  🎉 <killed> 🫥 <no_tests>  ⏰ <timeout>  🤔 <suspicious>  🙁 <survived>  🔇 <skipped>  🧙 <caught_by_type_check>

The line is rewritten in place while the run progresses, so the LAST
occurrence in the tee'd output is the final state.

Usage:
  python3 scripts/parse-mutmut-score.py --output <mutmut-output.txt>

Exit codes:
  0 — mutation score >= threshold (default: 80)
  1 — mutation score < threshold, or output not parseable
"""

import argparse
import re
import sys

MUTMUT3_LINE = re.compile(
    r'(\d+)/(\d+)\s+🎉\s*(\d+)\s+🫥\s*(\d+)\s+⏰\s*(\d+)\s+🤔\s*(\d+)\s+🙁\s*(\d+)\s+🔇\s*(\d+)\s+🧙\s*(\d+)'
)


def parse_mutmut_output(output_text):
    """Parse mutmut 3.x output and return (score, killed, total, survived)."""
    matches = MUTMUT3_LINE.findall(output_text)
    if not matches:
        return None, None, None, None

    # groups: checked, total, killed, no_tests, timeout, suspicious, survived, skipped, type_check
    _checked, _total, killed, _no_tests, timeout, suspicious, survived, _skipped, _type_check = (
        map(int, matches[-1])
    )

    # A suspicious mutant (flaky timing) is not proven killed — count it as
    # survived so the enforced score stays conservative.
    survived += suspicious

    total = killed + survived + timeout
    if total == 0:
        return 0, 0, 0, 0

    score = ((killed + timeout) / total) * 100
    return score, killed, total, survived


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, help='Path to mutmut output file')
    parser.add_argument('--threshold', type=int, default=80, help='Minimum mutation score (default: 80)')
    args = parser.parse_args()

    with open(args.output, encoding='utf-8', errors='replace') as f:
        output_text = f.read()

    score, killed, total, survived = parse_mutmut_output(output_text)

    if score is None:
        print('Could not parse mutation score from output')
        sys.exit(1)

    print(f'Mutation score: {score:.1f}% ({killed}/{total} killed, {survived} survived)')
    print(f'Threshold: {args.threshold}%')

    if score >= args.threshold:
        print(f'✅ PASS — mutation score {score:.1f}% >= {args.threshold}%')
        sys.exit(0)
    else:
        print(f'❌ FAIL — mutation score {score:.1f}% < {args.threshold}%')
        sys.exit(1)


if __name__ == '__main__':
    main()
