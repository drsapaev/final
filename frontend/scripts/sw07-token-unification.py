import re, os, sys

REPLACEMENTS = {
    '#007aff': 'var(--mac-accent-blue, #007aff)',
    '#3b82f6': 'var(--mac-accent-blue, #3b82f6)',
    '#2563eb': 'var(--mac-accent-blue, #2563eb)',
    '#0066cc': 'var(--mac-accent-blue, #0066cc)',
    '#2196f3': 'var(--mac-accent-blue, #2196f3)',
}
SKIP_DIRS = {'node_modules', 'dist', '__tests__', 'design-system', 'scripts', 'codemods', 'test'}
SKIP_EXT = {'.css', '.test.jsx', '.test.js', '.stories.jsx'}

def should_skip(fp):
    for d in SKIP_DIRS:
        if f'/{d}/' in fp: return True
    for e in SKIP_EXT:
        if fp.endswith(e): return True
    return False

def process(fp):
    with open(fp, 'r', encoding='utf-8') as f: content = f.read()
    orig = content; changes = 0
    for old, new in REPLACEMENTS.items():
        pat = r"(['\"])" + re.escape(old) + r"\1"
        rep = r"\1" + new + r"\1"
        c, n = re.subn(pat, rep, content)
        if n > 0: content = c; changes += n
    if content != orig:
        with open(fp, 'w', encoding='utf-8') as f: f.write(content)
        return changes
    return 0

src = sys.argv[1] if len(sys.argv) > 1 else 'src'
total = 0; files = 0
for root, dirs, flist in os.walk(src):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for fn in flist:
        if not (fn.endswith('.jsx') or fn.endswith('.js')): continue
        fp = os.path.join(root, fn)
        if should_skip(fp): continue
        c = process(fp)
        if c > 0: files += 1; total += c; print(f"  {fp}: {c}")
print(f"\nTotal: {total} replacements in {files} files")
