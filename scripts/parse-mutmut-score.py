#!/usr/bin/env python3
"""
Parse mutation score from mutmut output.

Usage:
  python3 scripts/parse-mutmut-score.py --output <mutmut-output.txt>

Exit codes:
  0 — mutation score >= threshold (default: 80)
  1 — mutation score < threshold
"""

import argparse
import re
import sys

def parse_mutmut_output(output_text):
    """Parse mutmut results to extract mutation score."""
    # mutmut output format: "⠋ 123/456 MUTATED  🎉 78 SURVIVED  ⏰ 0 TIMEOUT  🤔 0 SKIPPED"
    # or: "survived: 78, killed: 345, timeout: 0, skipped: 0"
    
    patterns = [
        r'(\d+)/(\d+)\s+MUTATED.*?(\d+)\s+SURVIVED.*?(\d+)\s+TIMEOUT.*?(\d+)\s+SKIPPED',
        r'killed:\s*(\d+).*?survived:\s*(\d+).*?timeout:\s*(\d+).*?skipped:\s*(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, output_text)
        if match:
            groups = match.groups()
            if 'MUTATED' in pattern:
                total = int(groups[1])
                killed = total - int(groups[2])  # total - survived
                timeout = int(groups[3])
                skipped = int(groups[4])
            else:
                killed = int(groups[0])
                survived = int(groups[1])
                timeout = int(groups[2])
                skipped = int(groups[3])
                total = killed + survived + timeout + skipped
            
            if total == 0:
                return 0, 0, 0, 0
            
            score = ((killed + timeout) / total) * 100
            return score, killed, total, survived
    
    return None, None, None, None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, help='Path to mutmut output file')
    parser.add_argument('--threshold', type=int, default=80, help='Minimum mutation score (default: 80)')
    args = parser.parse_args()

    with open(args.output) as f:
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
