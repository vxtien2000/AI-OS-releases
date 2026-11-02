#!/usr/bin/env python3
"""Site numbers from the Worker's Analytics Engine dataset "aios_site" (worker/index.js): page views and where they
came from, downloads per button, time on the page, how far people scroll and which sections they see.

    CLOUDFLARE_ACCOUNT_ID=... CLOUDFLARE_API_TOKEN=... tools/site-stats.py [days]     (default: 30)

The token needs the permission Account > Account Analytics > Read (Cloudflare dashboard > My Profile > API Tokens).
Also: GitHub's own count of each release zip (no token needed). Standard library only.
"""
import json
import os
import sys
import urllib.request

DATASET = "aios_site"
REPO = "vxtien2000/AI-OS-releases"
SECTIONS = ["hero", "run", "ask", "app", "speed", "tools", "needs", "dl"]  # page order, as in worker/index.js


def sql(query):
    account, token = os.environ.get("CLOUDFLARE_ACCOUNT_ID"), os.environ.get("CLOUDFLARE_API_TOKEN")
    if not account or not token:
        sys.exit("Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN (Account Analytics: Read).")
    req = urllib.request.Request(f"https://api.cloudflare.com/client/v4/accounts/{account}/analytics_engine/sql",
                                 data=query.encode(), method="POST", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.load(r)["data"]
    for row in rows:  # numbers may come back as text (64-bit sums)
        for k in ("n", "seconds", "depth", "w"):
            if k in row:
                row[k] = float(row[k] or 0)
        for k in ("button", "country", "ref", "sections", "tabs"):
            if k in row:
                row[k] = row[k] or ""
    return rows


def weighted_median(pairs):  # [(value, weight)]
    pairs = sorted(pairs)
    total, run = sum(w for _, w in pairs), 0
    for v, w in pairs:
        run += w
        if run >= total / 2:
            return v
    return 0


def report(days, downloads, views, engage, github):
    out = [f"AI-OS site, last {days} days (counts are estimates: Analytics Engine may sample)"]
    total = sum(r["n"] for r in views)
    out.append(f"\nPage views (browsers that run the page and do not ask not to be tracked): {total:g}")
    refs = {}
    for r in views:
        refs[r["ref"] or "(direct or same site)"] = refs.get(r["ref"] or "(direct or same site)", 0) + r["n"]
    for ref, n in sorted(refs.items(), key=lambda x: -x[1])[:10]:
        out.append(f"  {n:6g}  {ref}")
    countries = {}
    for r in views:
        countries[r["country"] or "?"] = countries.get(r["country"] or "?", 0) + r["n"]
    out.append("  countries: " + ", ".join(f"{c} {n:g}" for c, n in sorted(countries.items(), key=lambda x: -x[1])[:10]))

    dl = sum(r["n"] for r in downloads)
    out.append(f"\nDownloads through the site's /download: {dl:g}" + (f" ({100 * dl / total:.0f}% of views)" if total else ""))
    by = {}
    for r in downloads:
        by[r["button"]] = by.get(r["button"], 0) + r["n"]
    for b in ("hero", "footer", "direct"):
        out.append(f"  {by.get(b, 0):6g}  {b}" + ("  (a link elsewhere, for example the README)" if b == "direct" else " button"))

    w = sum(r["w"] for r in engage)
    out.append(f"\nEngagement ({w:g} page views measured when left)")
    if w:
        out.append(f"  time on the page: median {weighted_median([(r['seconds'], r['w']) for r in engage]):.0f} s, "
                   f"average {sum(r['seconds'] * r['w'] for r in engage) / w:.0f} s")
        out.append(f"  scrolled: median {weighted_median([(r['depth'], r['w']) for r in engage]):.0f}%, "
                   f"to the end (90% or more) {100 * sum(r['w'] for r in engage if r['depth'] >= 90) / w:.0f}%")
        out.append("  saw each section: " + ", ".join(
            f"{s} {100 * sum(r['w'] for r in engage if s in r['sections'].split(',')) / w:.0f}%" for s in SECTIONS))
        tabs = {}
        for r in engage:
            for t in filter(None, r["tabs"].split(",")):
                tabs[t] = tabs.get(t, 0) + r["w"]
        out.append("  opened tabs: " + (", ".join(f"{t} {n:g}" for t, n in tabs.items()) or "none"))

    out.append("\nGitHub's count of each zip (all time; also counts the app's own updates and direct downloads):")
    out += [f"  {line}" for line in github] or ["  (GitHub did not answer)"]
    return "\n".join(out)


def github_counts():
    try:
        with urllib.request.urlopen(f"https://api.github.com/repos/{REPO}/releases?per_page=10", timeout=20) as r:
            releases = json.load(r)
    except OSError:
        return []
    return [f"{rel['tag_name']}: " + ", ".join(f"{a['name']} {a['download_count']}" for a in rel.get("assets", [])
                                              if a["name"].endswith(".zip")) for rel in releases]


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    if not 1 <= days <= 90:  # Analytics Engine keeps three months
        sys.exit("days: 1 to 90")
    since = f"timestamp > NOW() - INTERVAL '{days}' DAY"
    downloads = sql(f"SELECT blob1 AS button, blob2 AS country, SUM(_sample_interval) AS n FROM {DATASET} "
                    f"WHERE index1 = 'download' AND {since} GROUP BY button, country")
    views = sql(f"SELECT blob1 AS ref, blob2 AS country, SUM(_sample_interval) AS n FROM {DATASET} "
                f"WHERE index1 = 'view' AND {since} GROUP BY ref, country")
    engage = sql(f"SELECT blob1 AS sections, blob2 AS tabs, double1 AS seconds, double2 AS depth, _sample_interval AS w "
                 f"FROM {DATASET} WHERE index1 = 'engage' AND {since} LIMIT 10000")
    print(report(days, downloads, views, engage, github_counts()))


if __name__ == "__main__":
    main()
