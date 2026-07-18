#!/usr/bin/env python3
"""
i18n_migrate.py — Batch migration of hardcoded Russian strings to i18n.

For each file:
  1. Find Russian strings in JSX text and string/template literals
     (skip lines that are pure comments and console/logger calls).
  2. Generate unique keys per file using a stable prefix.
  3. Replace the Russian strings with `t('misc.PREFIX_KEY')` calls.
  4. Append new keys to all 5 locale files (ru / uz-Latn / en / kk / uz-Cyrl).
  5. Add `const { t } = useTranslation();` if missing.

Usage:
  python3 i18n_migrate.py <file1.jsx> [<file2.jsx> ...]
"""

import os
import re
import sys

REPO = '/home/z/my-project/final-audit/frontend/src'
LOCALE_DIR = os.path.join(REPO, 'i18n', 'locales')
LOCALES = ['ru', 'uz-Latn', 'en', 'kk', 'uz-Cyrl']

# Russian Cyrillic detection
RU_RE = re.compile(r'[А-Яа-яЁё]{3,}')

# Patterns to skip
COMMENT_LINE_RE = re.compile(r'^\s*(//|/\*|\*)')
CONSOLE_LOG_RE = re.compile(r'(console|logger)\.(log|error|warn|debug|info)\s*\(')


def file_prefix(filepath):
    """Generate prefix from filename, e.g. LabPanel.jsx -> 'lp_'."""
    name = os.path.basename(filepath).replace('.jsx', '')
    # Split on camelCase and runs of uppercase letters
    # e.g. EMRStatusIndicator -> ['EMR', 'Status', 'Indicator']
    parts = re.findall(r'[A-Z]+(?=[A-Z][a-z]|\b)|[A-Z]?[a-z]+|[A-Z]+', name)
    if not parts:
        return name.lower()[:4] + '_'
    if len(parts) == 1:
        # Single word — use first 4 chars to avoid collisions
        return parts[0].lower()[:4] + '_'
    prefix = ''.join(p[0].lower() for p in parts)
    # Cap at 5 chars
    return prefix[:5] + '_'


def strip_inline_comment(line):
    """Strip // comments from a line, respecting string literals.
    Returns (code, comment) tuple."""
    in_str = None  # quote char or None
    i = 0
    while i < len(line):
        c = line[i]
        if in_str:
            if c == '\\':
                i += 2
                continue
            if c == in_str:
                in_str = None
            i += 1
            continue
        # not in string
        if c in '"\'`':
            in_str = c
            i += 1
            continue
        if c == '/' and i + 1 < len(line) and line[i + 1] == '/':
            return line[:i], line[i:]
        i += 1
    return line, ''


def find_russian_strings(src):
    """Yield tuples (line_no, line_text, kind, match_text, start_col, end_col).

    kind: 'jsx' (JSX text content) or 'str' (string literal).
    """
    lines = src.split('\n')
    for i, raw_line in enumerate(lines, 1):
        if COMMENT_LINE_RE.match(raw_line):
            continue
        if CONSOLE_LOG_RE.search(raw_line):
            continue
        # Strip inline // comment so strings inside it are ignored
        code, _comment = strip_inline_comment(raw_line)
        # Find JSX text content: >Russian text<
        for m in re.finditer(r'>([А-Яа-яЁё][^<>{}]*?)<', code):
            text = m.group(1)
            if RU_RE.search(text):
                yield (i, raw_line, 'jsx', text, m.start(1), m.end(1))
        # Find string literals with Russian
        # Single or double or backtick
        for m in re.finditer(
            r"""(?P<quote>['"`])(?P<body>(?:\\.|(?!(?P=quote)).)*?[А-Яа-яЁё](?:\\.|(?!(?P=quote)).)*?)(?P=quote)""",
            code,
            re.DOTALL,
        ):
            yield (i, raw_line, 'str', m.group(0), m.start(0), m.end(0))


def dedupe_keep_order(seq):
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def normalize_string(raw):
    """Given a raw quoted string like `'Привет'`, return (quote, body).
    Handles escapes minimally — we mostly deal with simple strings."""
    if not raw or raw[0] not in '"\'`':
        return None, None
    q = raw[0]
    body = raw[1:-1]
    # Unescape basic
    body = body.replace("\\'", "'").replace('\\"', '"').replace('\\`', '`')
    return q, body


def detect_template_interp(body):
    """Detect ${...} interpolations in a template literal body.
    Returns list of (full_match, inner_expr)."""
    return list(re.finditer(r'\$\{([^}]*)\}', body))


def slugify(text, max_len=28):
    """Turn Russian text into a slug (latin translit + words)."""
    # Simple translit map for common Russian letters
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
        'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k',
        'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
        'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '',
        'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    out = []
    for ch in text.lower():
        if ch in translit:
            out.append(translit[ch])
        elif ch.isalnum():
            out.append(ch)
        elif ch in ' _-':
            out.append('_')
        elif ch == '.':
            out.append('_')
        else:
            out.append('_')
    s = ''.join(out)
    s = re.sub(r'_+', '_', s).strip('_')
    if not s:
        s = 'text'
    return s[:max_len]


def collect_strings_for_file(src):
    """Return list of unique Russian string bodies (for str kind) and JSX texts."""
    strings = []
    jsx_texts = []
    seen_str = set()
    seen_jsx = set()
    for line_no, line, kind, text, sc, ec in find_russian_strings(src):
        if kind == 'jsx':
            t = text.strip()
            if t and t not in seen_jsx:
                seen_jsx.add(t)
                jsx_texts.append((line_no, t))
        else:
            q, body = normalize_string(text)
            if body is None:
                continue
            # Skip if it's a clearly technical string (URL, key path, etc.)
            # — keep all Russian strings since they're meaningful.
            if body not in seen_str:
                seen_str.add(body)
                strings.append((line_no, body, q))
    return strings, jsx_texts


def generate_keys(strings, jsx_texts, prefix, existing_keys):
    """Generate (key, body) entries. Returns list of (key, body, kind, original_q)."""
    keys = []
    used_keys = set(existing_keys)
    used_bodies = {}

    def make_key(slug_base, idx):
        base = f"{prefix}{slug_base}"
        # If we have multiple slugs that collide, append index
        candidate = base
        n = 2
        while candidate in used_keys:
            candidate = f"{base}_{n}"
            n += 1
        return candidate

    # Process strings
    slug_counts = {}
    for line_no, body, q in strings:
        slug = slugify(body)
        # Track slug counts to append suffix when collision
        slug_counts[slug] = slug_counts.get(slug, 0) + 1
        if slug_counts[slug] > 1:
            slug = f"{slug}_{slug_counts[slug]}"
        key = make_key(slug, 0)
        used_keys.add(key)
        keys.append({'key': key, 'body': body, 'kind': 'str', 'quote': q, 'line': line_no})

    # Process JSX texts (same slug space)
    for line_no, body in jsx_texts:
        slug = slugify(body)
        slug_counts[slug] = slug_counts.get(slug, 0) + 1
        if slug_counts[slug] > 1:
            slug = f"{slug}_{slug_counts[slug]}"
        key = make_key(slug, 0)
        used_keys.add(key)
        keys.append({'key': key, 'body': body, 'kind': 'jsx', 'quote': None, 'line': line_no})

    return keys


def build_locale_value(body, kind, quote):
    """Build the value to put in the locale file.

    For strings, store as-is with single quotes (escape internal apostrophes).
    For JSX text, store the trimmed text.
    For template literals, convert ${param} to {param}.
    """
    text = body
    if kind == 'str' and quote == '`':
        # Template literal — convert ${param} to {param}
        text = re.sub(r'\$\{([^}]*)\}', r'{\1}', text)
    # Escape single quotes for JS string literal
    text = text.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{text}'"


def build_replacement(entry):
    """Build the JS expression to replace the source text with.

    For str kind: t('misc.KEY') or t('misc.KEY', {param: expr, ...})
    For jsx kind: {t('misc.KEY')} or {t('misc.KEY', {...})}
    """
    key = entry['key']
    body = entry['body']
    quote = entry['quote']
    kind = entry['kind']

    # Extract interpolations from template literals
    if kind == 'str' and quote == '`':
        interps = detect_template_interp(body)
        if interps:
            # Build param object
            params = []
            used_names = set()
            for m in interps:
                expr = m.group(1).strip()
                # Generate a param name from the expression
                # Use last identifier in the expression
                idents = re.findall(r'[a-zA-Z_$][a-zA-Z0-9_$]*', expr)
                if idents:
                    name = idents[-1]
                else:
                    name = 'param'
                if name in used_names:
                    n = 2
                    while f"{name}_{n}" in used_names:
                        n += 1
                    name = f"{name}_{n}"
                used_names.add(name)
                params.append((name, expr))
            params_str = ', '.join(f"{n}: {e}" for n, e in params)
            expr = f"t('misc.{key}', {{ {params_str} }})"
        else:
            expr = f"t('misc.{key}')"
    else:
        expr = f"t('misc.{key}')"

    if kind == 'jsx':
        return '{' + expr + '}'
    return expr


def apply_replacements_to_source(src, entries_by_body):
    """Replace Russian strings in source with t() calls.

    entries_by_body: dict mapping body -> entry (for strings) and body -> entry (for JSX).
    """
    # Approach: process line by line, applying regex replacements
    # But we need to be careful about overlaps.

    new_lines = []
    for i, raw_line in enumerate(src.split('\n'), 1):
        if COMMENT_LINE_RE.match(raw_line):
            new_lines.append(raw_line)
            continue
        if CONSOLE_LOG_RE.search(raw_line):
            new_lines.append(raw_line)
            continue

        code, comment = strip_inline_comment(raw_line)

        # Replace JSX text first: >Russian text<
        def jsx_repl(m):
            text = m.group(1).strip()
            if text in entries_by_body.get('jsx', {}):
                entry = entries_by_body['jsx'][text]
                repl = build_replacement(entry)
                # Preserve leading/trailing whitespace
                lead = m.group(1)[:len(m.group(1)) - len(m.group(1).lstrip())]
                trail = m.group(1)[len(m.group(1).rstrip()):]
                return f'>{lead}{repl}{trail}<'
            return m.group(0)

        # Apply JSX replacement on code (without comment)
        code = re.sub(r'>([А-Яа-яЁё][^<>{}]*?)<', jsx_repl, code)

        # Replace string literals
        def str_repl(m):
            full = m.group(0)
            q = full[0]
            body = full[1:-1]
            # Unescape
            body = body.replace("\\'", "'").replace('\\"', '"').replace('\\`', '`')
            if body in entries_by_body.get('str', {}):
                entry = entries_by_body['str'][body]
                repl = build_replacement(entry)
                # Check if this is a JSX attribute value (e.g., title="...")
                # If preceded by `\w+=` (and not `\w+={`), wrap in {}.
                start = m.start()
                # Look back at the chars before the match
                prefix_code = code[:start].rstrip()
                # Match attribute= pattern (alphanum, underscore, dash, dot, colon) followed by =
                # but not ={ already (which would be a JSX expression container)
                if prefix_code and prefix_code[-1] == '=':
                    # Check if there's a { before = (e.g., already a JSX expression)
                    # We need to check: word= followed by quote
                    # match \w+= at end of prefix_code
                    if re.search(r'[\w.:-]+=$', prefix_code):
                        repl = '{' + repl + '}'
                return repl
            return full

        # Match quoted strings (handle escapes)
        code = re.sub(
            r"""(?P<q>['"`])(?:\\.|(?!(?P=q)).)*?[А-Яа-яЁё](?:\\.|(?!(?P=q)).)*?(?P=q)""",
            str_repl,
            code,
            re.DOTALL,
        )

        new_lines.append(code + comment)

    return '\n'.join(new_lines)


def ensure_use_translation(src):
    """Ensure file imports useTranslation and destructures t.

    Returns (new_src, was_modified).
    """
    new_src = src
    modified = False

    # Check for existing const { t } = useTranslation();
    has_destructure = re.search(r'const\s*\{\s*[^}]*\bt\b[^}]*\s*\}\s*=\s*useTranslation\s*\(\s*\)', src)

    # Check for useTranslation import
    has_import = re.search(r'import\s*\{[^}]*\buseTranslation\b[^}]*\}\s*from', src)

    if not has_import:
        # Add import after the last import statement (handle multi-line imports)
        lines = src.split('\n')
        last_import_end = -1
        in_import = False
        for i, ln in enumerate(lines):
            stripped = ln.strip()
            if in_import:
                # Check if this line closes the import (contains 'from ')
                if re.search(r'\bfrom\s+[\'"]', ln):
                    in_import = False
                    last_import_end = i
            elif stripped.startswith('import '):
                # Check if it's a single-line import
                if re.search(r'\bfrom\s+[\'"]', ln) or stripped.endswith(';'):
                    last_import_end = i
                else:
                    # Multi-line import - wait for closing 'from'
                    in_import = True
        import_line = "import { useTranslation } from '{PATH}';"
        if last_import_end >= 0:
            lines.insert(last_import_end + 1, import_line)
        else:
            lines.insert(0, import_line)
        new_src = '\n'.join(lines)
        modified = True

    if not has_destructure:
        # Add const { t } = useTranslation(); at the top of the first function/component body
        # Look for "function ComponentName(" or "const ComponentName = ("
        # Insert after the opening block.
        # Strategy: find first occurrence of "function X(...)" or "const X = (..." with a { body
        lines = new_src.split('\n')

        # Find insertion point: just inside the first component's body
        insert_idx = -1
        insert_line = None
        # Pattern 1: function Name(props) { on a single line
        for i, ln in enumerate(lines):
            m = re.match(r'(\s*)(export\s+)?(default\s+)?function\s+([A-Z]\w*)\s*\([^)]*\)\s*\{', ln)
            if m:
                indent = m.group(1) + '  '
                insert_idx = i + 1
                insert_line = f"{indent}const {{ t }} = useTranslation();"
                break
            # const X = (...) => { on a single line
            m = re.match(r'(\s*)(export\s+)?(default\s+)?const\s+([A-Z]\w*)\s*=\s*\([^)]*\)\s*=>\s*\{', ln)
            if m:
                indent = m.group(1) + '  '
                insert_idx = i + 1
                insert_line = f"{indent}const {{ t }} = useTranslation();"
                break
            # const X = ({  ...multi-line args... }) => {  -- need to find matching )
            m = re.match(r'(\s*)(export\s+)?(default\s+)?const\s+([A-Z]\w*)\s*=\s*\(([^)]*)$', ln)
            if m:
                # Walk forward to find the closing ) => {
                j = i + 1
                paren_depth = 1  # we've seen one (
                while j < len(lines):
                    for c in lines[j]:
                        if c == '(':
                            paren_depth += 1
                        elif c == ')':
                            paren_depth -= 1
                            if paren_depth == 0:
                                break
                    if paren_depth == 0:
                        # Check this line contains ) => {
                        if re.search(r'\)\s*=>\s*\{', lines[j]):
                            indent = m.group(1) + '  '
                            insert_idx = j + 1
                            insert_line = f"{indent}const {{ t }} = useTranslation();"
                        break
                    j += 1
                if insert_idx >= 0:
                    break
            # function Name(args) with newline before {
            m = re.match(r'(\s*)(export\s+)?(default\s+)?function\s+([A-Z]\w*)\s*\(([^)]*)$', ln)
            if m:
                # Walk forward to find closing ) {
                j = i + 1
                paren_depth = 1
                while j < len(lines):
                    for c in lines[j]:
                        if c == '(':
                            paren_depth += 1
                        elif c == ')':
                            paren_depth -= 1
                            if paren_depth == 0:
                                break
                    if paren_depth == 0:
                        if re.search(r'\)\s*\{', lines[j]):
                            indent = m.group(1) + '  '
                            insert_idx = j + 1
                            insert_line = f"{indent}const {{ t }} = useTranslation();"
                        break
                    j += 1
                if insert_idx >= 0:
                    break

        if insert_idx >= 0 and insert_line:
            lines.insert(insert_idx, insert_line)
            new_src = '\n'.join(lines)
            modified = True

    return new_src, modified


def compute_import_path(filepath):
    """Compute the relative path from a file to ../i18n/useTranslation."""
    # filepath is relative to REPO
    depth = filepath.count('/')
    if depth == 0:
        return './i18n/useTranslation'
    elif depth == 1:
        return '../i18n/useTranslation'
    elif depth == 2:
        return '../../i18n/useTranslation'
    elif depth == 3:
        return '../../../i18n/useTranslation'
    else:
        return '../' * (depth) + 'i18n/useTranslation'


def load_locale_keys():
    """Load existing keys from misc section of ru.js to avoid collisions."""
    ru_path = os.path.join(LOCALE_DIR, 'ru.js')
    with open(ru_path, encoding='utf-8') as f:
        content = f.read()
    # Find misc: { ... }
    m = re.search(r'\bmisc:\s*\{(.*?)\n  \},', content, re.DOTALL)
    if not m:
        return set()
    body = m.group(1)
    keys = set(re.findall(r'^\s*([a-z_][a-z0-9_]*)\s*:', body, re.MULTILINE))
    return keys


def append_to_locale(locale, entries, comment):
    """Append entries to misc section of locale file."""
    path = os.path.join(LOCALE_DIR, f'{locale}.js')
    with open(path, encoding='utf-8') as f:
        content = f.read()
    # Find misc: { ... }
    # We need to insert before the closing `  },` of misc section.
    # Strategy: find `misc: {` line, then find the next line that is exactly `  },`
    lines = content.split('\n')
    misc_start = -1
    for i, ln in enumerate(lines):
        if re.match(r'\s*misc:\s*\{', ln):
            misc_start = i
            break
    if misc_start < 0:
        raise RuntimeError(f"misc section not found in {path}")
    # Find the closing brace
    misc_end = -1
    for i in range(misc_start + 1, len(lines)):
        if re.match(r'\s*\},?\s*$', lines[i]) and '}' in lines[i] and '{' not in lines[i]:
            misc_end = i
            break
    if misc_end < 0:
        raise RuntimeError(f"misc section end not found in {path}")

    # Build insertion text
    insert_lines = []
    insert_lines.append(f'    // {comment}')
    for entry in entries:
        val = build_locale_value(entry['body'], entry['kind'], entry['quote'])
        insert_lines.append(f"    {entry['key']}: {val},")

    # Insert before misc_end
    lines[misc_end:misc_end] = insert_lines
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def process_file(filepath, prefix_override=None, dry_run=False):
    """Process one file."""
    full_path = os.path.join(REPO, filepath) if not filepath.startswith(REPO) else filepath
    if not os.path.exists(full_path):
        print(f"  ✗ File not found: {full_path}")
        return None

    with open(full_path, encoding='utf-8') as f:
        src = f.read()

    prefix = prefix_override or file_prefix(filepath)
    existing_keys = load_locale_keys()

    strings, jsx_texts = collect_strings_for_file(src)
    if not strings and not jsx_texts:
        print(f"  · {filepath}: no Russian strings found")
        return None

    entries = generate_keys(strings, jsx_texts, prefix, existing_keys)
    if not entries:
        print(f"  · {filepath}: no entries generated")
        return None

    # Build body -> entry maps
    entries_by_body = {'str': {}, 'jsx': {}}
    for e in entries:
        if e['kind'] == 'str':
            entries_by_body['str'][e['body']] = e
        else:
            entries_by_body['jsx'][e['body']] = e

    # Apply replacements
    new_src = apply_replacements_to_source(src, entries_by_body)

    # Add useTranslation import/hook
    # Need import path
    rel_path = full_path.replace(REPO + '/', '')
    import_path = compute_import_path(rel_path)
    new_src, added_hook = ensure_use_translation(new_src)
    # Replace placeholder with actual import path
    new_src = new_src.replace("import { useTranslation } from '{PATH}';",
                              f"import {{ useTranslation }} from '{import_path}';")

    if not dry_run:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(new_src)
        # Append to all locale files
        # ru.js: actual Russian content
        # uz-Latn.js: Uzbek translation (we use Russian as fallback for now per task spec)
        # en.js, kk.js, uz-Cyrl.js: Russian fallback
        comment = f"{os.path.basename(filepath)} ({prefix})"
        append_to_locale('ru', entries, comment)
        append_to_locale('uz-Latn', entries, comment)
        append_to_locale('en', entries, comment)
        append_to_locale('kk', entries, comment)
        append_to_locale('uz-Cyrl', entries, comment)

    print(f"  ✓ {filepath}: {len(entries)} keys (prefix={prefix})")
    return entries


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    files = sys.argv[1:]
    total = 0
    for fp in files:
        # Normalize path
        if fp.startswith(REPO):
            rel = fp.replace(REPO + '/', '')
        elif fp.startswith('./'):
            rel = fp[2:]
        else:
            rel = fp
        entries = process_file(rel)
        if entries:
            total += len(entries)
    print(f"\nTotal: {total} keys added across {len(files)} files")


if __name__ == '__main__':
    main()
