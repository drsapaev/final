#!/usr/bin/env python3
"""
Admin CSS migration script.
Replaces `style={{...}}` blocks in JSX files with className="admin-..." classes,
adding new classes to admin.css as needed. Handles dynamic values via CSS custom
property injection (style={{ '--admin-x': val }}).
"""
import os
import re
import sys
import json
import hashlib

ADMIN_CSS = "frontend/src/components/admin/admin.css"
ADMIN_DIR = "frontend/src/components/admin"

# ---- Load existing classes from admin.css ----
def load_existing_classes(path):
    classes = set()
    with open(path, "r") as f:
        for line in f:
            m = re.match(r'^\.([\w-]+)\s*\{', line)
            if m:
                classes.add(m.group(1))
    return classes

# ---- Property value normalization & class-name token generation ----
VALUE_MAP = {
    # colors
    'var(--mac-text-primary)': 'primary',
    'var(--mac-text-secondary)': 'secondary',
    'var(--mac-text-tertiary)': 'tertiary',
    'var(--mac-text-on-accent)': 'on-accent',
    'var(--mac-danger)': 'error',
    'var(--mac-error)': 'error',
    'var(--mac-success)': 'success',
    'var(--mac-warning)': 'warning',
    'var(--mac-info)': 'info',
    'var(--mac-accent)': 'accent',
    'var(--mac-accent-blue)': 'blue',
    'var(--mac-accent-purple)': 'purple',
    'var(--mac-accent-orange)': 'orange',
    'var(--mac-accent-green)': 'green',
    'var(--mac-card-bg)': 'card-bg',
    'var(--mac-card-border)': 'card-border',
    'var(--mac-bg-primary)': 'bg-primary',
    'var(--mac-bg-secondary)': 'bg-secondary',
    'var(--mac-bg-tertiary)': 'bg-tertiary',
    'var(--mac-border-color)': 'border',
    'var(--mac-border-light)': 'border-light',
    'var(--mac-font-size-xs)': 'xs',
    'var(--mac-font-size-sm)': 'sm',
    'var(--mac-font-size-base)': 'base',
    'var(--mac-font-size-lg)': 'lg',
    'var(--mac-font-size-xl)': 'xl',
    'var(--mac-font-size-2xl)': '2xl',
    'var(--mac-font-weight-regular)': '400',
    'var(--mac-font-weight-medium)': 'med',
    'var(--mac-font-weight-semibold)': 'semi',
    'var(--mac-font-weight-bold)': 'bold',
    'transparent': 'transparent',
    'inherit': 'inherit',
    'none': 'none',
    'auto': 'auto',
    'white': 'white',
    'block': 'block',
    'inline': 'inline',
    'inline-block': 'inline-block',
    'inline-flex': 'inline-flex',
    'flex': 'flex',
    'grid': 'grid',
    'center': 'center',
    'row': 'row',
    'column': 'column',
    'wrap': 'wrap',
    'nowrap': 'nowrap',
    'pointer': 'pointer',
    'default': 'default',
    'normal': 'normal',
    'italic': 'italic',
    'bold': 'bold',
    'underline': 'underline',
    'hidden': 'hidden',
    'scroll': 'scroll',
    'visible': 'visible',
    'baseline': 'baseline',
    'stretch': 'stretch',
    'space-between': 'between',
    'space-around': 'around',
    'space-evenly': 'evenly',
    'flex-start': 'start',
    'flex-end': 'end',
    'middle': 'middle',
    'top': 'top',
    'bottom': 'bottom',
    'left': 'left',
    'right': 'right',
    'relative': 'relative',
    'absolute': 'absolute',
    'fixed': 'fixed',
    'sticky': 'sticky',
    'static': 'static',
    'monospace': 'mono',
    'nowrap': 'nowrap',
    'pre': 'pre',
    'pre-wrap': 'pre-wrap',
    'break-word': 'break-word',
    'ellipsis': 'ellipsis',
    'clip': 'clip',
    'capitalize': 'capitalize',
    'uppercase': 'uppercase',
    'lowercase': 'lowercase',
    'solid': 'solid',
    'dashed': 'dashed',
    'dotted': 'dotted',
    'double': 'double',
    'groove': 'groove',
    'ridge': 'ridge',
    'inset': 'inset',
    'outset': 'outset',
    'circle': 'circle',
    'cover': 'cover',
    'contain': 'contain',
    'fill': 'fill',
    'linear': 'linear',
    'ease': 'ease',
    'ease-in': 'ease-in',
    'ease-out': 'ease-out',
    'ease-in-out': 'ease-in-out',
    'infinite': 'infinite',
    'forwards': 'forwards',
    'backwards': 'backwards',
    'both': 'both',
    'alternate': 'alternate',
    'reverse': 'reverse',
    'rotate(180deg)': 'rot180',
    'rotate(90deg)': 'rot90',
    'rotate(-90deg)': 'rot-90',
    'rotate(45deg)': 'rot45',
    'rotate(-45deg)': 'rot-45',
    'scale(1.05)': 'scale105',
    'scale(0.95)': 'scale95',
    'scale(1.1)': 'scale110',
    'capitalize': 'cap',
    'nowrap': 'nowrap',
}

def normalize_value(v):
    """Return (is_static, token, css_value, custom_prop_name_if_dynamic)."""
    v = v.strip()
    # remove trailing comma
    if v.endswith(','):
        v = v[:-1].strip()
    # String literal: 'foo' or "foo"
    m = re.match(r"^'([^']*)'$", v) or re.match(r'^"([^"]*)"$', v)
    if m:
        s = m.group(1)
        return True, value_token(s), s, None
    # Number
    if re.match(r'^-?\d+(\.\d+)?$', v):
        return True, value_token(v), v, None
    # var(--mac-*) or var(--admin-*)
    if re.match(r'^var\(--[\w-]+\)$', v):
        return True, value_token(v), v, None
    # Known keyword
    if v in VALUE_MAP:
        return True, VALUE_MAP[v], v, None
    # Simple hex color
    if re.match(r'^#[0-9a-fA-F]{3,8}$', v):
        return True, 'hex' + v[1:], v, None
    # rgba/rgb/hsl
    if re.match(r'^(rgba?|hsla?)\([^)]+\)$', v):
        return True, 'color', v, None
    # calc()
    if re.match(r'^calc\([^)]+\)$', v):
        return True, 'calc', v, None
    # px/em/rem/%/vh/vw values
    if re.match(r'^-?\d+(\.\d+)?(px|em|rem|%|vh|vw|vmin|vmax|pt|deg|s|ms|fr)$', v):
        return True, value_token(v), v, None
    # repeat(...) for grid
    if re.match(r'^repeat\(', v):
        return True, 'gridrepeat', v, None
    # linear-gradient / radial-gradient
    if re.match(r'^[a-z-]+-gradient\(', v):
        return True, 'gradient', v, None
    # animation shorthand like "spin 1s linear infinite"
    if re.match(r'^[\w-]+\s+\d', v):
        return True, 'anim', v, None
    # Anything else with letters/braces/etc. => dynamic
    return False, None, None, None

def value_token(v):
    """Generate a short token from a static value."""
    v = str(v)
    if v in VALUE_MAP:
        return VALUE_MAP[v]
    # px values: 24px -> 24, 1.5px -> 1p5
    m = re.match(r'^(-?\d+(?:\.\d+)?)(px|em|rem|%|vh|vw|pt|deg|s|ms|fr)?$', v)
    if m:
        num = m.group(1)
        unit = m.group(2) or ''
        # compact number
        num = num.replace('.', 'p')
        if num.startswith('-'):
            num = 'n' + num[1:]
        if unit == 'px':
            return num
        if unit == '%':
            return num + 'pct'
        return num + unit
    return re.sub(r'[^a-zA-Z0-9]+', '-', v).strip('-')[:20]

PROP_ABBREV = {
    'color': '',
    'background': 'bg',
    'backgroundColor': 'bgc',
    'background-color': 'bgc',
    'borderColor': 'bd-c',
    'border-color': 'bd-c',
    'border': 'bd',
    'borderRadius': 'radius',
    'border-radius': 'radius',
    'borderTop': 'bd-t',
    'borderBottom': 'bd-b',
    'borderLeft': 'bd-l',
    'borderRight': 'bd-r',
    'borderWidth': 'bd-w',
    'borderStyle': 'bd-s',
    'padding': 'p',
    'paddingTop': 'pt',
    'paddingBottom': 'pb',
    'paddingLeft': 'pl',
    'paddingRight': 'pr',
    'margin': 'm',
    'marginTop': 'mt',
    'marginBottom': 'mb',
    'marginLeft': 'ml',
    'marginRight': 'mr',
    'width': 'w',
    'height': 'h',
    'minWidth': 'minw',
    'maxWidth': 'maxw',
    'minHeight': 'minh',
    'maxHeight': 'maxh',
    'fontSize': 'fs',
    'font-size': 'fs',
    'fontWeight': 'fw',
    'font-weight': 'fw',
    'fontFamily': 'ff',
    'font-family': 'ff',
    'fontStyle': 'fst',
    'lineHeight': 'lh',
    'letterSpacing': 'ls',
    'display': 'd',
    'flexDirection': 'fd',
    'flex-direction': 'fd',
    'flexWrap': 'fw',
    'justifyContent': 'jc',
    'justify-content': 'jc',
    'alignItems': 'ai',
    'align-items': 'ai',
    'alignContent': 'ac',
    'alignSelf': 'as',
    'flex': 'flex',
    'flexGrow': 'fg',
    'flexShrink': 'fsk',
    'flexBasis': 'fb',
    'gap': 'gap',
    'gridTemplateColumns': 'gtc',
    'grid-template-columns': 'gtc',
    'gridTemplateRows': 'gtr',
    'gridColumn': 'gc',
    'gridRow': 'gr',
    'gridColumnGap': 'gcg',
    'gridRowGap': 'grg',
    'position': 'pos',
    'top': 'top',
    'bottom': 'bottom',
    'left': 'left',
    'right': 'right',
    'zIndex': 'z',
    'z-index': 'z',
    'opacity': 'op',
    'overflow': 'ov',
    'overflowX': 'ovx',
    'overflowY': 'ovy',
    'overflow-wrap': 'ovw',
    'whiteSpace': 'ws',
    'white-space': 'ws',
    'textOverflow': 'to',
    'text-overflow': 'to',
    'textDecoration': 'td',
    'text-decoration': 'td',
    'textTransform': 'tt',
    'text-transform': 'tt',
    'textAlign': 'ta',
    'text-align': 'ta',
    'textShadow': 'tsh',
    'boxShadow': 'bsh',
    'box-shadow': 'bsh',
    'boxSizing': 'bsz',
    'cursor': 'cur',
    'transform': 'tf',
    'transition': 'tr',
    'animation': 'anim',
    'animationName': 'anim-n',
    'animationDuration': 'anim-d',
    'animationTimingFunction': 'anim-tf',
    'animationIterationCount': 'anim-ic',
    'animationFillMode': 'anim-fm',
    'listStyle': 'ls',
    'listStyleType': 'lst',
    'objectFit': 'of',
    'objectPosition': 'op',
    'userSelect': 'us',
    'user-select': 'us',
    'pointerEvents': 'pe',
    'pointer-events': 'pe',
    'visibility': 'vis',
    'verticalAlign': 'va',
    'vertical-align': 'va',
    'wordBreak': 'wb',
    'word-break': 'wb',
    'resize': 'rz',
    'outline': 'ol',
    'filter': 'flt',
    'backdropFilter': 'bflt',
    'writingMode': 'wm',
    'aspectRatio': 'ar',
    'aspect-ratio': 'ar',
    'tableLayout': 'tl',
    'borderCollapse': 'bc',
    'borderSpacing': 'bs',
    'content': 'ct',
    'willChange': 'wc',
    'stroke': 'stroke',
    'fill': 'fill',
    'clipPath': 'cp',
    'clip-path': 'cp',
    'WebkitLineClamp': 'wlc',
    'WebkitBoxOrient': 'wbo',
    'gridColumnStart': 'gcs',
    'gridColumnEnd': 'gce',
    'gridRowStart': 'grs',
    'gridRowEnd': 'gre',
    'inset': 'inset',
    'insetInlineStart': 'iis',
    'insetInlineEnd': 'iie',
    'gridArea': 'ga',
    'gridTemplateAreas': 'gta',
    'placeItems': 'pi',
    'placeContent': 'pc',
    'placeSelf': 'ps',
    'order': 'ord',
    'isolation': 'iso',
    'mixBlendMode': 'mbm',
    'backgroundImage': 'bgi',
    'background-image': 'bgi',
    'backgroundSize': 'bgs',
    'background-size': 'bgs',
    'backgroundPosition': 'bgp',
    'background-position': 'bgp',
    'backgroundRepeat': 'bgr',
    'background-clip': 'bgcl',
    'backgroundClip': 'bgcl',
    'wordWrap': 'ww',
    'word-wrap': 'ww',
    'hyphens': 'hy',
}

def prop_token(prop):
    """Convert a CSS-in-JS property name to a short token."""
    # camelCase or kebab
    if prop in PROP_ABBREV:
        return PROP_ABBREV[prop]
    # fallback: kebab-ize camelCase
    s = re.sub(r'([A-Z])', r'-\1', prop).lower()
    if s in PROP_ABBREV:
        return PROP_ABBREV[s]
    return s.replace('-', '')[:8]

# ---- parse style block content into (prop, raw_value) pairs ----
def split_top_level(s, sep=','):
    """Split string on `sep` at top level (respecting (), {}, [], '', "")."""
    parts = []
    depth = 0
    in_squote = False
    in_dquote = False
    buf = []
    i = 0
    while i < len(s):
        c = s[i]
        if in_squote:
            buf.append(c)
            if c == "'":
                in_squote = False
        elif in_dquote:
            buf.append(c)
            if c == '"':
                in_dquote = False
        else:
            if c == "'":
                in_squote = True
                buf.append(c)
            elif c == '"':
                in_dquote = True
                buf.append(c)
            elif c in '([{':
                depth += 1
                buf.append(c)
            elif c in ')]}':
                depth -= 1
                buf.append(c)
            elif c == sep and depth == 0:
                parts.append(''.join(buf))
                buf = []
            else:
                buf.append(c)
        i += 1
    if buf:
        parts.append(''.join(buf))
    return parts

def parse_style_block(content):
    """
    content: the inner text between style={{ and }} (excluding both).
    Returns list of (prop, raw_value_string) tuples.
    """
    pairs = []
    parts = split_top_level(content, ',')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # spread operator {...x} — treat as dynamic whole
        if part.startswith('...'):
            pairs.append(('__spread__', part))
            continue
        # split on first colon at top level
        sub = split_top_level(part, ':')
        if len(sub) < 2:
            # shorthand: { color } => { color: color }
            if re.match(r'^[a-zA-Z_$][\w$]*$', part):
                pairs.append((part, part))
            continue
        prop = sub[0].strip()
        val = ':'.join(sub[1:]).strip()
        pairs.append((prop, val))
    return pairs

# ---- find style={{...}} blocks in source, respecting brace balance ----
def find_style_blocks(src):
    """
    Returns list of (start_index, end_index_exclusive, inner_content).
    start_index points at 'style', end_index is right after closing '}}'.
    """
    results = []
    i = 0
    n = len(src)
    while i < n:
        # find 'style={{'
        idx = src.find('style={{', i)
        if idx == -1:
            break
        # ensure not inside a string/comment — simplistic check; assume code is clean
        start = idx
        inner_start = idx + len('style={{')
        # walk to find matching }}
        depth = 1
        j = inner_start
        in_squote = False
        in_dquote = False
        in_bquote = False
        while j < n and depth > 0:
            c = src[j]
            if in_squote:
                if c == "'":
                    in_squote = False
                elif c == '\\':
                    j += 1
            elif in_dquote:
                if c == '"':
                    in_dquote = False
                elif c == '\\':
                    j += 1
            elif in_bquote:
                if c == '`':
                    in_bquote = False
                elif c == '\\':
                    j += 1
            else:
                if c == "'":
                    in_squote = True
                elif c == '"':
                    in_dquote = True
                elif c == '`':
                    in_bquote = True
                elif c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        # this } closes the second { of {{
                        # check next char is also }
                        if j + 1 < n and src[j+1] == '}':
                            inner = src[inner_start:j]
                            end = j + 2
                            results.append((start, end, inner))
                            i = end
                            break
                        else:
                            # malformed; treat as not a match
                            i = j + 1
                            break
            j += 1
        else:
            # ran off end
            break
        if not results or results[-1][1] != end if results else True:
            pass
        # advance i if not advanced
        if i <= idx:
            i = idx + 1
    return results

# ---- build class name and CSS rule ----
def build_classname_and_rule(pairs, existing_classes, new_classes):
    """
    pairs: list of (prop, raw_value, custom_prop_name_or_None)
    Returns (classname, css_rule_text, leftover_dynamic_style_str_or_None).
    leftover_dynamic_style_str is the inline `style={{ '--admin-x': val }}` for dynamic props only.
    """
    static_parts = []  # (prop, token, css_value)
    dynamic_parts = []  # (prop, raw_value, custom_prop_name)
    has_spread = False
    for entry in pairs:
        if len(entry) == 3:
            prop, val, cp = entry
        else:
            prop, val = entry
            cp = None
        if prop == '__spread__':
            has_spread = True
            continue
        is_static, token, css_val, _ = normalize_value(val)
        if is_static:
            static_parts.append((prop, token, css_val))
        else:
            dynamic_parts.append((prop, val, cp))

    # If there's a spread, we cannot safely convert — return None to skip
    if has_spread:
        return None, None, None

    # Build static class name
    name_tokens = []
    css_decls = []
    for prop, token, css_val in static_parts:
        pt = prop_token(prop)
        if pt == '':
            name_tokens.append(token)
        else:
            name_tokens.append(f"{pt}-{token}" if token else pt)
        # convert camelCase prop to kebab-case for CSS
        css_prop = re.sub(r'([A-Z])', r'-\1', prop).lower()
        css_decls.append(f"  {css_prop}: {css_val};")

    # Add dynamic var usages to css_decls and name
    for prop, val, cp in dynamic_parts:
        css_prop = re.sub(r'([A-Z])', r'-\1', prop).lower()
        pt = prop_token(prop)
        if pt == '':
            pt = 'col'
        css_decls.append(f"  {css_prop}: var({cp});")
        name_tokens.append(f"{pt}-dyn")

    if not name_tokens:
        return None, None, None

    # Build a base name
    base = 'admin-' + '-'.join(name_tokens)
    # sanitize
    base = re.sub(r'[^a-zA-Z0-9-]+', '-', base).strip('-')
    # truncate to reasonable length
    if len(base) > 180:
        # hash-based suffix
        h = hashlib.md5(base.encode()).hexdigest()[:8]
        base = base[:160] + '-' + h

    # ensure uniqueness against existing + new
    classname = base
    counter = 1
    while classname in existing_classes or classname in new_classes:
        # if the existing class has the same name, check if css rule matches
        if classname in existing_classes:
            # accept it — assume identical (deterministic generation)
            break
        classname = f"{base}-{counter}"
        counter += 1

    css_rule = f".{classname} {{\n" + "\n".join(css_decls) + "\n}\n"

    # Build leftover dynamic style
    leftover = None
    if dynamic_parts:
        items = []
        for prop, val, cp in dynamic_parts:
            items.append(f"'{cp}': {val}")
        leftover = "{{ " + ", ".join(items) + " }}"

    return classname, css_rule, leftover

def assign_custom_props(pairs):
    """Assign --admin-* custom property names to dynamic props. Returns new pairs list with cp filled."""
    out = []
    dyn_counter = 0
    for prop, val in pairs:
        if prop == '__spread__':
            out.append((prop, val, None))
            continue
        is_static, _, _, _ = normalize_value(val)
        if is_static:
            out.append((prop, val, None))
        else:
            pt = prop_token(prop)
            if pt == '':
                pt = 'col'
            cp = f"--admin-{pt}{dyn_counter}"
            dyn_counter += 1
            out.append((prop, val, cp))
    return out

def extract_object_definitions(src):
    """
    Scan source for `const NAME = { ... }` and `const OBJ = { key: { ... }, ... }`.
    Returns dict mapping reference name → raw inner property text.
    e.g. { 'adminSectionShellStyle': "background: '...', border: '...'",
           'styles.colorOption': "display: 'flex', ..." }
    Only extracts OBJECT literal values (not arrays/primitives).
    """
    defs = {}
    # find `const NAME = {` patterns (also `let NAME = {`)
    for m in re.finditer(r'\b(?:const|let)\s+(\w+)\s*=\s*\{', src):
        name = m.group(1)
        open_brace = m.end() - 1
        body, end = _extract_balanced(src, open_brace)
        if body is None:
            continue
        # Check if body looks like a flat style object (keys are CSS props)
        # vs a nested object (keys are arbitrary names mapping to objects)
        # Heuristic: if any top-level value is itself an object literal {...}, treat as nested
        nested = _is_nested_object(body)
        if nested:
            # parse keys: NAME: { ... }
            for km in re.finditer(r'(\w+)\s*:\s*\{', body):
                kname = km.group(1)
                kopen = km.end() - 1
                kbody, _ = _extract_balanced(body, kopen)
                if kbody is not None:
                    defs[f"{name}.{kname}"] = kbody
        else:
            defs[name] = body
    return defs

def _extract_balanced(src, open_idx):
    """Given index of '{', return (inner_text, index_after_closing_brace)."""
    if open_idx >= len(src) or src[open_idx] != '{':
        return None, open_idx
    depth = 1
    j = open_idx + 1
    in_s = in_d = in_b = False
    n = len(src)
    while j < n and depth > 0:
        c = src[j]
        if in_s:
            if c == "'": in_s = False
            elif c == '\\': j += 1
        elif in_d:
            if c == '"': in_d = False
            elif c == '\\': j += 1
        elif in_b:
            if c == '`': in_b = False
            elif c == '\\': j += 1
        else:
            if c == "'": in_s = True
            elif c == '"': in_d = True
            elif c == '`': in_b = True
            elif c == '{': depth += 1
            elif c == '}': depth -= 1
        j += 1
    if depth != 0:
        return None, open_idx
    return src[open_idx+1:j-1], j

def _is_nested_object(body):
    """Return True if any top-level value in the object body is itself {...}."""
    parts = split_top_level(body, ',')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # find first ':' at top level
        sub = split_top_level(part, ':')
        if len(sub) < 2:
            continue
        val = ':'.join(sub[1:]).strip()
        if val.startswith('{'):
            return True
    return False

def resolve_spreads(pairs, defs):
    """
    Given pairs (list of (prop, raw_value)), resolve any '__spread__' entries
    by inlining properties from defs. Returns new pairs list.
    """
    out = []
    for prop, val in pairs:
        if prop == '__spread__':
            # val is like '...NAME' or '...styles.key'
            ref = val.strip().lstrip('.').strip()
            # the val starts with '...' ; extract ref name
            mm = re.match(r'\.\.\.\s*([\w.]+)', val)
            if not mm:
                # unknown spread — keep as spread (will be skipped later)
                out.append((prop, val))
                continue
            ref = mm.group(1)
            if ref in defs:
                # inline the raw body
                body = defs[ref]
                sub_pairs = parse_style_block(body)
                out.extend(sub_pairs)
            else:
                # cannot resolve — keep as spread
                out.append((prop, val))
        else:
            out.append((prop, val))
    # check if any unresolved spreads remain
    return out

# ---- find className to merge with ----
def find_classname_at(src, style_start):
    """
    Given that style_start points at 'style', look backwards for className="..." or className={'...'}
    WITHIN THE SAME JSX TAG (i.e., no '>' between className and style).
    Returns (cn_start, cn_end, existing_classname_value, quote_style) or None.
    """
    # search backwards up to 400 chars for 'className', stopping at '>' (tag boundary)
    window_start = max(0, style_start - 400)
    window = src[window_start:style_start]
    # walk backwards; if we hit '>' first, no className in this tag
    idx = window.rfind('className')
    if idx == -1:
        return None
    # Check there's no '>' between className and style_start (same tag)
    segment = window[idx:]
    if '>' in segment:
        return None
    # also check there's no '<' after the className's '<' — i.e., className is inside a tag
    # find the '<' that opens this tag (before className)
    tag_open = window.rfind('<', 0, idx)
    if tag_open == -1:
        return None
    abs_idx = window_start + idx
    # parse after 'className'
    j = abs_idx + len('className')
    while j < len(src) and src[j] in ' \t\n':
        j += 1
    if j >= len(src):
        return None
    if src[j] == '=':
        j += 1
        while j < len(src) and src[j] in ' \t\n':
            j += 1
        if j >= len(src):
            return None
        if src[j] == '"' or src[j] == "'":
            q = src[j]
            k = j + 1
            while k < len(src) and src[k] != q:
                k += 1
            return (abs_idx, k + 1, src[j+1:k], q)
        elif src[j] == '{':
            depth = 1
            k = j + 1
            in_s = in_d = in_b = False
            while k < len(src) and depth > 0:
                c = src[k]
                if in_s:
                    if c == "'": in_s = False
                    elif c == '\\': k += 1
                elif in_d:
                    if c == '"': in_d = False
                    elif c == '\\': k += 1
                elif in_b:
                    if c == '`': in_b = False
                    elif c == '\\': k += 1
                else:
                    if c == "'": in_s = True
                    elif c == '"': in_d = True
                    elif c == '`': in_b = True
                    elif c == '{': depth += 1
                    elif c == '}': depth -= 1
                k += 1
            inner = src[j+1:k-1].strip()
            if (inner.startswith("'") and inner.endswith("'")) or (inner.startswith('"') and inner.endswith('"')):
                return (abs_idx, k, inner[1:-1], None)
            if inner.startswith('`') and inner.endswith('`'):
                return None
            return None
    return None

# ---- main migration per file ----
def migrate_file(filepath, existing_classes, new_classes):
    with open(filepath, 'r') as f:
        src = f.read()
    original_count = src.count('style={{')

    # Extract local object definitions for spread resolution
    defs = extract_object_definitions(src)

    blocks = find_style_blocks(src)
    if not blocks:
        return 0, 0, []

    # Process from end to start to keep indices valid
    blocks = list(reversed(blocks))
    replaced = 0
    skipped = 0
    skip_reasons = []
    for start, end, inner in blocks:
        pairs = parse_style_block(inner)
        if not pairs:
            skipped += 1
            skip_reasons.append(f"empty pairs at {start}")
            continue
        # Resolve spreads using local definitions
        pairs = resolve_spreads(pairs, defs)
        # Check for remaining unresolved spreads
        if any(p == '__spread__' for p, _ in pairs):
            skipped += 1
            skip_reasons.append(f"unresolved spread at {start}: {inner[:80]}")
            continue
        pairs_with_cp = assign_custom_props(pairs)
        classname, css_rule, leftover = build_classname_and_rule(pairs_with_cp, existing_classes, new_classes)
        if classname is None:
            skipped += 1
            skip_reasons.append(f"unconvertible at {start}: {inner[:60]}")
            continue

        # Register new class
        if classname not in existing_classes and classname not in new_classes:
            new_classes[classname] = css_rule
        elif classname in new_classes:
            # already added — ensure css rule matches (it should, deterministic)
            pass

        # Find existing className to merge with
        cn_info = find_classname_at(src, start)

        # Build replacement
        # We replace [className="..." ]? style={{...}} with className="merged" [style={{'--admin-x':val}}]?
        # But the className and style might not be adjacent. We handle them separately:
        # 1. Replace the style={{...}} block (start..end) with either nothing (if no leftover) or leftover style
        # 2. If className exists, merge classname into it. If not, insert className before style position.

        # Determine the existing className value
        existing_cn = ""
        if cn_info:
            existing_cn = cn_info[2] or ""

        # Merge
        if existing_cn:
            merged = (existing_cn + " " + classname).strip()
            # Quote style: if original was double-quoted, keep it
            q = cn_info[3]
            if q == '"':
                new_cn_str = f'className="{merged}"'
            elif q == "'":
                new_cn_str = f"className='{merged}'"
            else:
                new_cn_str = f'className="{merged}"'
        else:
            new_cn_str = f'className="{classname}"'

        # Build the style replacement
        if leftover:
            style_replacement = f'style={leftover}'
        else:
            style_replacement = ''

        # Now perform edits. We have up to two regions to modify:
        # Region A: className (cn_info[0]..cn_info[1]) if present
        # Region B: style (start..end)
        # They may overlap only if className is before style (typical). They should not overlap.
        if cn_info:
            cn_start, cn_end = cn_info[0], cn_info[1]
            # ensure ordering
            if cn_end <= start:
                # replace style first (later in string), then className
                # replace style region
                src = src[:start] + style_replacement + src[end:]
                # recompute cn indices — they are before start, unchanged
                src = src[:cn_start] + new_cn_str + src[cn_end:]
            else:
                # overlap — skip to be safe
                skipped += 1
                skip_reasons.append(f"overlap at {start}")
                continue
        else:
            # no className — replace style with className + optional leftover
            if leftover:
                replacement = f'{new_cn_str} {style_replacement}'
            else:
                replacement = new_cn_str
            src = src[:start] + replacement + src[end:]

        replaced += 1

    new_count = src.count('style={{')
    # Only write if changed
    with open(filepath, 'w') as f:
        f.write(src)
    return original_count, replaced, skip_reasons

def main():
    files = sys.argv[1:]
    if not files:
        print("usage: migrate_admin_css.py <file1.jsx> [file2.jsx ...]")
        sys.exit(1)
    existing = load_existing_classes(ADMIN_CSS)
    new_classes = {}
    total_before = 0
    total_replaced = 0
    for f in files:
        before, replaced, reasons = migrate_file(f, existing, new_classes)
        total_before += before
        total_replaced += replaced
        print(f"{os.path.basename(f)}: before={before} replaced={replaced} remaining={before-replaced}")
        for r in reasons[:3]:
            print(f"  skip: {r}")
    # Append new classes to admin.css
    if new_classes:
        with open(ADMIN_CSS, 'a') as f:
            f.write("\n/* ─── Batch 5 additions ─── */\n")
            for name in sorted(new_classes.keys()):
                f.write("\n" + new_classes[name])
    print(f"\nTOTAL: before={total_before} replaced={total_replaced} new_classes={len(new_classes)}")

if __name__ == '__main__':
    main()
