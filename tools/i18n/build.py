#!/usr/bin/env python3
"""Build the site's translated pages: each English page in PAGES -> site/<lang>/<file> for every language in LANGS.

tools/i18n/<lang>.json holds {"strings": {English: translation}, "keep": [strings left as they are], "decimal": ","}.
A string is replaced only where it is a whole text node or a whole attribute value (alt, aria-label, content, title,
placeholder, data-alt, data-t-*), never inside <code>, <pre>, <script> or <style>. The build stops when a translation
no longer matches anything in the English pages (the English changed: translate it again), and lists every visible
string that has no translation, so nothing is left in English by accident.

In every page, English included, the language menu and the hreflang links come from LANGS and PAGES, and in a
translated page the links to the other translated pages stay in its language. Adding a language: one entry in LANGS
and one JSON file. Adding a page: one entry in PAGES (its English file needs the i18n markers and data-localized).

  python3 tools/i18n/build.py          # build every language; exit 1 on a stale or missing translation
"""
import html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.normpath(os.path.join(HERE, "..", "..", "site"))
ORIGIN = "https://aiosqa.dpdns.org"
LANGS = [  # code, the name in its own language, the folder ("" for English), og:locale
    ("en", "English", "", "en_US"),
    ("vi", "Tiếng Việt", "vi", "vi_VN"),
]
PAGES = [  # English file, its address
    ("index.html", "/"),
    ("privacy.html", "/privacy"),
    ("feedback.html", "/feedback"),
]
MENU_LABEL = {"en": "Language", "vi": "Ngôn ngữ"}
ATTRS = ("alt", "aria-label", "content", "title", "placeholder", "data-alt", "data-label", "data-t-[a-z]+")
SKIP = re.compile(r"<(script|style|code|pre)\b.*?</\1>", re.S)
TEXT = re.compile(r">([^<]+)<")
ATTR = re.compile(r'\s(%s)="([^"]*)"' % "|".join(ATTRS))


def address(folder, page):
    """/vi/ for the home page in Vietnamese, /vi/privacy for its privacy page; English has no folder."""
    if not folder:
        return page
    return f"/{folder}/" if page == "/" else f"/{folder}{page}"


def switcher(cur, page):
    current = ' aria-current="page"'
    items = "\n".join(f'          <li><a href="{address(f, page)}" hreflang="{c}" lang="{c}"{current if c == cur else ""}>{n}</a></li>'
                      for c, n, f, l in LANGS)
    name = next(n for c, n, f, l in LANGS if c == cur)
    return (f'<!-- i18n:switcher -->\n      <details class="langs">\n        <summary aria-label="{MENU_LABEL.get(cur, "Language")}: '
            f'{name}"><span aria-hidden="true">{cur.upper()}</span></summary>\n        <ul>\n{items}\n        </ul>\n'
            f'      </details>\n      <!-- /i18n:switcher -->')


def alternates(page):
    rows = [f'<link rel="alternate" hreflang="{c}" href="{ORIGIN}{address(f, page)}">' for c, n, f, l in LANGS]
    rows.append(f'<link rel="alternate" hreflang="x-default" href="{ORIGIN}{page}">')
    return "<!-- i18n:alternates -->\n" + "\n".join(rows) + "\n<!-- /i18n:alternates -->"


def shared(doc, cur, page):
    doc = re.sub(r"<!-- i18n:switcher -->.*?<!-- /i18n:switcher -->", lambda m: switcher(cur, page), doc, flags=re.S)
    return re.sub(r"<!-- i18n:alternates -->.*?<!-- /i18n:alternates -->", lambda m: alternates(page), doc, flags=re.S)


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

    blocks = []

    def hold(m):  # code, scripts and styles wait outside; their opening tag's attributes still count (<code title>)
        block = m.group(0)
        head_end = block.index(">") + 1
        blocks.append(ATTR.sub(attr, block[:head_end]) + block[head_end:])
        return f"<!--i18n-hold-{len(blocks) - 1}-->"

    held = SKIP.sub(hold, doc)  # a placeholder keeps the < and > around the text next to it, so that text is seen too
    out = ATTR.sub(attr, TEXT.sub(text, held))
    out = re.sub(r"<!--i18n-hold-(\d+)-->", lambda m: blocks[int(m.group(1))], out)
    return out, used, missing


def build(code, folder, locale, spec, file, page):
    src = open(os.path.join(SITE, file), encoding="utf-8").read()
    src = re.sub(r"<!-- i18n:switcher -->.*?<!-- /i18n:switcher -->", "<!-- i18n:switcher --><!-- /i18n:switcher -->", src,
                 flags=re.S)  # made per language below, not translated
    doc, used, missing = translate(src, spec["strings"], set(spec.get("keep", [])))
    here = address(folder, page)
    doc = doc.replace('<html lang="en" data-localized>', f'<html lang="{code}" data-localized>', 1)
    doc = doc.replace('data-decimal="."', f'data-decimal="{spec.get("decimal", ".")}"')  # 22.7 s, written the local way
    doc = doc.replace(f'<link rel="canonical" href="{ORIGIN}{page}">', f'<link rel="canonical" href="{ORIGIN}{here}">', 1)
    doc = doc.replace(f'<meta property="og:url" content="{ORIGIN}{page}">', f'<meta property="og:url" content="{ORIGIN}{here}">', 1)
    doc = doc.replace('<meta property="og:locale" content="en_US">', f'<meta property="og:locale" content="{locale}">', 1)
    # links to the site's other translated pages stay in this language; /download, /releases and the rest do not change
    for f2, p2 in PAGES:
        target = address(folder, p2)
        doc = re.sub(r'(\shref=")%s(#[^"]*)?"' % re.escape(p2), lambda m: f'{m.group(1)}{target}{m.group(2) or ""}"', doc)
    # the page sits one folder down: its own files are reached from the site's root
    doc = re.sub(r'(\s(?:src|srcset|poster)=")(images/)', r"\1/\2", doc)
    doc = re.sub(r'url\("\./', 'url("/', doc)
    relative = re.findall(r'\s(?:src|srcset|poster|href)="(?!https?:|/|#|mailto:)([^"]+)"', doc)
    if relative:
        sys.exit(f"{code}/{file}: these paths would break one folder down: {sorted(set(relative))}")
    doc = shared(doc, code, page)
    os.makedirs(os.path.join(SITE, folder), exist_ok=True)
    open(os.path.join(SITE, folder, file), "w", encoding="utf-8").write(doc)
    return used, missing


def main():
    for file, page in PAGES:  # the English pages: menu and hreflang links
        path = os.path.join(SITE, file)
        src = open(path, encoding="utf-8").read()
        fixed = shared(src, "en", page)
        if fixed != src:
            open(path, "w", encoding="utf-8").write(fixed)
            print(f"site/{file}: language menu and hreflang links updated")
    js = os.path.join(SITE, "lang.js")
    homes = json.dumps({c: address(f, "/") for c, n, f, l in LANGS}, ensure_ascii=False)
    old = open(js, encoding="utf-8").read()
    new = re.sub(r"/\* i18n:homes \*/.*?/\* /i18n:homes \*/", "/* i18n:homes */" + homes + "/* /i18n:homes */", old)
    if new != old:
        open(js, "w", encoding="utf-8").write(new)
        print("site/lang.js: homes updated")
    bad = False
    for code, name, folder, locale in LANGS[1:]:
        spec = json.load(open(os.path.join(HERE, f"{code}.json"), encoding="utf-8"))
        used_all = set()
        for file, page in PAGES:
            used, missing = build(code, folder, locale, spec, file, page)
            used_all |= used
            print(f"site/{folder}/{file} built ({name})")
            for k in dict.fromkeys(missing):
                bad = True
                print(f"  NOT TRANSLATED: {k[:110]}")
        for k in spec["strings"]:
            if k not in used_all:
                bad = True
                print(f"  STALE (no longer in the English pages): {k[:100]}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
