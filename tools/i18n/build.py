#!/usr/bin/env python3
"""Build translated copies of the landing page: site/index.html (English, the only source) -> site/<lang>/index.html.

tools/i18n/<lang>.json holds {"strings": {English: translation}, "keep": [strings left as they are], "meta": {...}}.
A string is replaced only where it is a whole text node or a whole attribute value (alt, aria-label, content, title,
data-alt, data-t-*), never inside <code>, <pre>, <script> or <style>. The build stops when a translation no longer
matches anything in the English page (the English changed: translate it again), and lists every visible string that
has no translation, so nothing is left in English by accident. The language menu and the hreflang links in every page,
English included, come from LANGS below: adding a language is one entry here and one JSON file.

  python3 tools/i18n/build.py          # build every language; exit 1 on a stale or missing translation
"""
import html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "..", "..", "site")
ORIGIN = "https://aiosqa.dpdns.org"
LANGS = [  # code, the name in its own language, path, og:locale
    ("en", "English", "/", "en_US"),
    ("vi", "Tiếng Việt", "/vi/", "vi_VN"),
]
ATTRS = ("alt", "aria-label", "content", "title", "data-alt", "data-t-passed", "data-t-step", "data-t-play", "data-t-pause")
SKIP = re.compile(r"<(script|style|code|pre)\b.*?</\1>", re.S)
TEXT = re.compile(r">([^<]+)<")
ATTR = re.compile(r'\s(%s)="([^"]*)"' % "|".join(re.escape(a) for a in ATTRS))


def switcher(cur):
    name = next(n for c, n, p, l in LANGS if c == cur)
    current = ' aria-current="page"'
    items = "\n".join(f'          <li><a href="{p}" hreflang="{c}" lang="{c}"{current if c == cur else ""}>{n}</a></li>'
                      for c, n, p, l in LANGS)
    label = {"en": "Language", "vi": "Ngôn ngữ"}.get(cur, "Language")
    return (f'<!-- i18n:switcher -->\n      <details class="langs">\n        <summary aria-label="{label}: {name}"><span '
            f'aria-hidden="true">{cur.upper()}</span></summary>\n        <ul>\n{items}\n        </ul>\n      </details>\n'
            f'      <!-- /i18n:switcher -->')


def alternates():
    rows = [f'<link rel="alternate" hreflang="{c}" href="{ORIGIN}{p}">' for c, n, p, l in LANGS]
    rows.append(f'<link rel="alternate" hreflang="x-default" href="{ORIGIN}/">')
    return "<!-- i18n:alternates -->\n" + "\n".join(rows) + "\n<!-- /i18n:alternates -->"


def shared(doc, cur):
    doc = re.sub(r"<!-- i18n:switcher -->.*?<!-- /i18n:switcher -->", lambda m: switcher(cur), doc, flags=re.S)
    return re.sub(r"<!-- i18n:alternates -->.*?<!-- /i18n:alternates -->", lambda m: alternates(), doc, flags=re.S)


def translate(doc, strings, keep):
    used, missing = set(), []

    def text(m):
        raw = m.group(1)
        key = html.unescape(raw.strip())
        if key in strings:
            used.add(key)
            lead, trail = raw[:len(raw) - len(raw.lstrip())], raw[len(raw.rstrip()):]
            return ">" + lead + html.escape(strings[key], quote=False) + trail + "<"
        if key and key not in keep and re.search(r"[A-Za-z]", key):
            missing.append(key)
        return m.group(0)

    def attr(m):
        key = html.unescape(m.group(2))
        if key in strings:
            used.add(key)
            return f' {m.group(1)}="{html.escape(strings[key], quote=True)}"'
        if key and key not in keep and re.search(r"[A-Za-z]", key) and (m.group(1) != "content" or " " in key):
            missing.append(f"@{m.group(1)}: {key}")  # a meta's content counts only when it is a sentence
        return m.group(0)

    out, last = [], 0
    for m in SKIP.finditer(doc):  # translate only outside code, scripts and styles
        out.append(ATTR.sub(attr, TEXT.sub(text, doc[last:m.start()])))
        start = m.group(0)
        head_end = start.index(">") + 1  # the opening tag's own attributes still count (a <code title="...">)
        out.append(ATTR.sub(attr, start[:head_end]) + start[head_end:])
        last = m.end()
    out.append(ATTR.sub(attr, TEXT.sub(text, doc[last:])))
    return "".join(out), used, missing


def build(code, path, locale):
    spec = json.load(open(os.path.join(HERE, f"{code}.json"), encoding="utf-8"))
    src = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
    src = re.sub(r"<!-- i18n:switcher -->.*?<!-- /i18n:switcher -->", "<!-- i18n:switcher --><!-- /i18n:switcher -->", src,
                 flags=re.S)  # made per language below, not translated
    doc, used, missing = translate(src, spec["strings"], set(spec.get("keep", [])))
    stale = [k for k in spec["strings"] if k not in used]
    doc = doc.replace('<html lang="en" data-localized>', f'<html lang="{code}" data-localized>', 1)
    doc = doc.replace('data-decimal="."', f'data-decimal="{spec.get("decimal", ".")}"')  # the demo's 22.7 s, written the local way
    doc = doc.replace(f'<link rel="canonical" href="{ORIGIN}/">', f'<link rel="canonical" href="{ORIGIN}{path}">', 1)
    doc = doc.replace(f'<meta property="og:url" content="{ORIGIN}/">', f'<meta property="og:url" content="{ORIGIN}{path}">', 1)
    doc = doc.replace('<meta property="og:locale" content="en_US">', f'<meta property="og:locale" content="{locale}">', 1)
    # the page sits one folder down: its own files are reached from the site's root
    doc = re.sub(r'(\s(?:src|srcset|poster)=")(images/)', r"\1/\2", doc)
    doc = re.sub(r'url\("\./', 'url("/', doc)  # a stylesheet the English page reaches as ./x.css
    relative = re.findall(r'\s(?:src|srcset|poster|href)="(?!https?:|/|#|mailto:)([^"]+)"', doc)
    if relative:
        sys.exit(f"{code}: these paths would break one folder down: {sorted(set(relative))}")
    doc = re.sub(r'(<a class="wordmark" href=")#main(")', r"\1" + path + r"#main\2", doc)
    doc = shared(doc, code)
    os.makedirs(os.path.join(SITE, code), exist_ok=True)
    open(os.path.join(SITE, code, "index.html"), "w", encoding="utf-8").write(doc)
    return stale, missing


def main():
    en = os.path.join(SITE, "index.html")
    src = open(en, encoding="utf-8").read()
    fixed = shared(src, "en")
    if fixed != src:
        open(en, "w", encoding="utf-8").write(fixed)
        print("site/index.html: language menu and hreflang links updated")
    js = os.path.join(SITE, "lang.js")
    homes = json.dumps({c: p for c, n, p, l in LANGS}, ensure_ascii=False)
    old = open(js, encoding="utf-8").read()
    new = re.sub(r"/\* i18n:homes \*/.*?/\* /i18n:homes \*/", "/* i18n:homes */" + homes + "/* /i18n:homes */", old)
    if new != old:
        open(js, "w", encoding="utf-8").write(new)
        print("site/lang.js: homes updated")
    bad = False
    for code, name, path, locale in LANGS[1:]:
        stale, missing = build(code, path, locale)
        print(f"site/{code}/index.html built ({name})")
        for k in stale:
            bad = True
            print(f"  STALE (no longer in the English page): {k[:100]}")
        for k in dict.fromkeys(missing):
            bad = True
            print(f"  NOT TRANSLATED: {k[:100]}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
