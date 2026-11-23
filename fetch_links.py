#!/usr/bin/env python3
"""Reads links.txt (one URL per line) and writes links.json with
title, author, source, date and description taken from each page's metadata.

Run locally:  python3 fetch_links.py
Or let the GitHub Action in .github/workflows/links.yml run it when links.txt changes.

Override anything the page gets wrong by adding  | key=value  after the URL:
  https://example.com/story | author=Jane Doe | title=A better title
"""
import json
import sys
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse


class Meta(HTMLParser):
    def __init__(self):
        super().__init__()
        self.m, self.title, self._in_title = {}, "", False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content") and key not in self.m:
                self.m[key] = a["content"].strip()
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def scrape(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; cv-link-fetcher)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read(600_000).decode(r.headers.get_content_charset() or "utf-8", "replace")
    p = Meta()
    p.feed(html)
    m = p.m
    pick = lambda *keys: next((m[k] for k in keys if k in m), "")
    return {
        "url": url,
        "title": pick("og:title", "twitter:title") or p.title.strip(),
        "author": pick("author", "article:author", "citation_author"),
        "source": pick("og:site_name", "application-name") or urlparse(url).netloc.removeprefix("www."),
        "description": pick("og:description", "description", "twitter:description"),
        "date": pick("article:published_time", "citation_publication_date", "date")[:10],
    }


items = []
for line in open("links.txt", encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    url, *overrides = [x.strip() for x in line.split("|")]
    try:
        item = scrape(url)
    except Exception as e:
        print("Could not read", url, "-", e, file=sys.stderr)
        item = {"url": url, "title": url, "source": urlparse(url).netloc.removeprefix("www.")}
    for o in overrides:
        k, _, v = o.partition("=")
        item[k.strip()] = v.strip()
    items.append(item)

with open("links.json", "w", encoding="utf-8") as f:
    json.dump(items, f, indent=2, ensure_ascii=False)
print("Wrote", len(items), "links to links.json")
