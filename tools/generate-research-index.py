#!/usr/bin/env python3
"""Build the public article index from published page metadata."""
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ''
        self.description = ''
        self.canonical = ''
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'title':
            self.in_title = True
        if tag == 'meta' and attrs.get('name') == 'description':
            self.description = attrs.get('content', '')
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonical = attrs.get('href', '')

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data

def build_papers(directory, previous):
    prior = {p['slug']: p for p in previous}
    papers = []
    for path in sorted(directory.glob('*.html')):
        if path.name in {'index.html', 'overview.html'}:
            continue
        raw = path.read_text(encoding='utf-8')
        meta = Metadata()
        meta.feed(raw)
        date = re.search(r'"datePublished"\s*:\s*"([^"]+)"', raw)
        expected = 'https://8bitconcepts.com/research/' + path.name
        if not meta.title or not meta.description or not date or meta.canonical != expected:
            raise ValueError('Missing or inconsistent article metadata: ' + path.name)
        published = date.group(1)
        datetime.fromisoformat(published.replace('Z', '+00:00'))
        title = re.sub(r'\s+(?:--|—|\|)\s+8bitconcepts$', '', meta.title).strip()
        papers.append({'slug':path.stem, 'title':title, 'summary':meta.description,
                       'url':expected, 'tags':prior.get(path.stem, {}).get('tags', []),
                       'date_published':published})
    if not papers:
        raise ValueError('No article pages found')
    return sorted(papers, key=lambda p:(p['date_published'], p['slug']))

def main():
    output = ROOT / 'research.json'
    manifest = json.loads(output.read_text())
    papers = build_papers(ROOT / 'research', manifest.get('papers', []))
    if manifest.get('papers') == papers and manifest.get('total') == len(papers):
        print('Research index already current: %d articles' % len(papers))
        return
    manifest.update(papers=papers, total=len(papers), updated_at=datetime.now(timezone.utc).isoformat())
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print('Updated research index: %d articles' % len(papers))

if __name__ == '__main__':
    main()
