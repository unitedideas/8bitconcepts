#!/usr/bin/env python3
"""
8bitconcepts Research Pipeline — autonomous AI research paper generation.

Researches trending AI/ML topics, writes research papers in the
8bitconcepts house style, adds them to the site, and deploys via git push.

Usage:
    python3 research-pipeline.py generate          # Generate one new paper
    python3 research-pipeline.py generate --topic "Agent evaluation frameworks"
    python3 research-pipeline.py list-topics        # Show topic ideas
    python3 research-pipeline.py dry-run             # Generate without saving

Requires:
    - Anthropic API key (keychain: anthropic-api-key)
    - Brave Search API key (keychain: brave-search-api-key)
"""

import argparse
import gzip
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
RESEARCH_DIR = SCRIPT_DIR / "research"
INDEX_HTML = SCRIPT_DIR / "index.html"
TOPICS_LOG = SCRIPT_DIR / "research" / ".topics-generated.json"


def get_secret(service):
    result = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-a", "foundry", "-s", service, "-w"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR: '{service}' not found in keychain", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def brave_search(query, count=10):
    """Search using Brave Search API."""
    api_key = get_secret("brave-search-api-key")
    params = urllib.parse.urlencode({"q": query, "count": count})
    url = f"https://api.search.brave.com/res/v1/web/search?{params}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    })
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            data = json.loads(raw)
            results = []
            for r in data.get("web", {}).get("results", []):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "description": r.get("description", ""),
                })
            return results
    except urllib.error.HTTPError as e:
        print(f"Brave Search error: {e.code}", file=sys.stderr)
        return []


def fetch_page_text(url, max_chars=8000):
    """Fetch a page and extract text content."""
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.7.1"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            # Strip HTML tags
            text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:max_chars]
    except Exception:
        return ""


def send_discord_alert(message):
    """Send alert to Discord via Owl Bot."""
    try:
        token = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-a", "foundry", "-s", "discord-bot-token", "-w"],
            capture_output=True, text=True
        ).stdout.strip()
        channel = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-a", "foundry", "-s", "discord-channel-id", "-w"],
            capture_output=True, text=True
        ).stdout.strip()
        if token and channel:
            payload = json.dumps({"content": message[:1900]}).encode()
            req = urllib.request.Request(
                f"https://discord.com/api/v10/channels/{channel}/messages",
                data=payload,
                headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def call_claude(messages, max_tokens=8192, model="claude-sonnet-4-6"):
    """Call Claude API directly."""
    api_key = get_secret("anthropic-api-key")
    payload = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }).encode()

    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload, headers={
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        if e.code == 400 and ("credit" in body.lower() or "billing" in body.lower()):
            print(f"Anthropic API credits exhausted. Skipping this run.", file=sys.stderr)
            send_discord_alert("**8bitconcepts Research Pipeline** — skipped: Anthropic API credits exhausted. Refill at console.anthropic.com.")
            sys.exit(0)
        print(f"Claude API error {e.code}: {body[:500]}", file=sys.stderr)
        raise


def get_existing_topics():
    """Get list of existing research paper topics to avoid duplicates."""
    topics = []
    for f in RESEARCH_DIR.glob("*.html"):
        with open(f) as fh:
            content = fh.read()
            title_match = re.search(r"<h1>(.*?)</h1>", content)
            if title_match:
                topics.append(title_match.group(1))
    return topics


def load_topics_log():
    if TOPICS_LOG.exists():
        with open(TOPICS_LOG) as f:
            return json.load(f)
    return []


def save_topics_log(entries):
    with open(TOPICS_LOG, "w") as f:
        json.dump(entries, f, indent=2)


def generate_topic():
    """Use Claude + search to find a compelling new research topic."""
    existing = get_existing_topics()
    existing_str = "\n".join(f"- {t}" for t in existing)

    # Search for current AI trends
    trends = brave_search("AI enterprise adoption challenges 2026", count=5)
    trends += brave_search("LLM production engineering problems 2026", count=5)
    trends += brave_search("agentic AI organizational impact 2026", count=5)

    search_context = "\n".join(
        f"- {r['title']}: {r['description']}" for r in trends[:12]
    )

    prompt = f"""You are a research director at 8bitconcepts, an AI enablement consulting firm.
Your audience is engineering leaders and CTOs at Series B-D companies deploying AI.

Existing papers (DO NOT repeat these topics):
{existing_str}

Current AI landscape signals from search:
{search_context}

Generate ONE compelling research paper topic. Requirements:
1. Addresses a real, specific pain point in enterprise AI adoption/deployment
2. Has a clear, provocative thesis (not just "here's a survey of X")
3. Can be backed with data from public reports (McKinsey, Gartner, a]16z, etc.)
4. Written for practitioners, not academics
5. Has a hook — a surprising stat, counterintuitive finding, or specific case study
6. Different from all existing papers listed above

Return JSON only:
{{
  "title": "The Paper Title",
  "slug": "the-paper-slug",
  "tag": "Category Tag (e.g., MLOps, Engineering Maturity, Cost Analysis)",
  "eyebrow": "Research — Category",
  "subtitle": "One-paragraph hook that makes someone want to read the whole thing",
  "thesis": "The core argument in 2-3 sentences",
  "key_data_points": ["stat or finding 1", "stat or finding 2", "stat or finding 3"],
  "search_queries": ["query to find supporting data 1", "query 2", "query 3"]
}}"""

    result = call_claude([{"role": "user", "content": prompt}])
    # Extract JSON from response
    json_match = re.search(r"\{[\s\S]*\}", result)
    if json_match:
        return json.loads(json_match.group())
    raise ValueError(f"Failed to parse topic JSON from Claude response: {result[:200]}")


def research_topic(topic):
    """Gather research data for a topic using web search."""
    research_data = []

    # Search using the topic's suggested queries
    for query in topic.get("search_queries", []):
        results = brave_search(query, count=5)
        for r in results[:3]:
            page_text = fetch_page_text(r["url"])
            research_data.append({
                "source": r["title"],
                "url": r["url"],
                "description": r["description"],
                "excerpt": page_text[:3000] if page_text else "",
            })

    # Also search for the topic title directly
    direct_results = brave_search(topic["title"] + " enterprise AI", count=5)
    for r in direct_results[:2]:
        page_text = fetch_page_text(r["url"])
        research_data.append({
            "source": r["title"],
            "url": r["url"],
            "description": r["description"],
            "excerpt": page_text[:3000] if page_text else "",
        })

    return research_data


def write_paper(topic, research_data):
    """Generate the full HTML research paper."""
    # Read an existing paper as a style template
    template_file = RESEARCH_DIR / "the-measurement-problem.html"
    with open(template_file) as f:
        template_html = f.read()

    # Extract just the CSS and structure (not content)
    css_match = re.search(r"<style>(.*?)</style>", template_html, re.DOTALL)
    css = css_match.group(1) if css_match else ""

    # Get existing paper titles for "related" section
    existing = get_existing_topics()
    existing_files = list(RESEARCH_DIR.glob("*.html"))
    related_papers = []
    for f in existing_files[:3]:
        with open(f) as fh:
            content = fh.read()
            title_match = re.search(r"<h1>(.*?)</h1>", content)
            tag_match = re.search(r'class="meta-tag">(.*?)</span>', content)
            if title_match:
                related_papers.append({
                    "file": f.name,
                    "title": title_match.group(1),
                    "tag": tag_match.group(1) if tag_match else "Research",
                })

    research_context = ""
    sources = []
    for i, rd in enumerate(research_data[:8]):
        research_context += f"\n--- Source {i+1}: {rd['source']} ---\n"
        research_context += f"URL: {rd['url']}\n"
        research_context += f"Summary: {rd['description']}\n"
        if rd.get("excerpt"):
            research_context += f"Content: {rd['excerpt'][:2000]}\n"
        sources.append({"title": rd["source"], "url": rd["url"]})

    related_html = ""
    for rp in related_papers:
        related_html += f'''      <a class="related-card" href="/research/{rp['file']}">
        <div class="related-card-title">{rp['title']}</div>
        <div class="related-card-sub">{rp['tag']}</div>
      </a>\n'''

    month_year = datetime.now().strftime("%B %Y")

    prompt = f"""You are a senior research writer at 8bitconcepts, an AI enablement consulting firm.
Write a complete research paper in HTML format.

TOPIC:
Title: {topic['title']}
Tag: {topic['tag']}
Eyebrow: {topic['eyebrow']}
Subtitle: {topic['subtitle']}
Thesis: {topic['thesis']}

RESEARCH DATA (use these as sources — cite them in footnotes):
{research_context}

STYLE REQUIREMENTS:
- Practitioner-focused, not academic. Write for the CTO who has 15 minutes.
- Data-driven: include specific numbers, percentages, dollar amounts where possible.
- Opinionated: take a clear position. "Most companies do X. They should do Y instead."
- Use concrete examples and case studies (anonymized if needed).
- ~2,500-3,500 words in the article body.
- Include 3-4 stat boxes (stat-row with stat-box elements).
- Include 1-2 callout blocks (div class="callout").
- Include at least one data table or question block.
- End with actionable recommendations (not just "here's the problem").
- Include footnotes referencing the source URLs.

RELATED PAPERS HTML (insert as-is in related section):
{related_html}

OUTPUT FORMAT:
Return ONLY the complete HTML document. Use this exact structure:

<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{topic['title']} -- 8bitconcepts</title>
  <meta name="description" content="[subtitle text]" />
  <link rel="canonical" href="https://8bitconcepts.com/research/{topic['slug']}.html" />
  <meta property="og:title" content="{topic['title']} — 8bitconcepts" />
  <meta property="og:description" content="[subtitle text]" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="https://8bitconcepts.com/research/{topic['slug']}.html" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="{topic['title']}" />
  <meta name="twitter:description" content="[subtitle text]" />
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "ScholarlyArticle",
    "headline": "{topic['title']}",
    "url": "https://8bitconcepts.com/research/{topic['slug']}.html",
    "datePublished": "{topic.get('date','2026-04-01')}",
    "author": {{
      "@type": "Organization",
      "name": "8bitconcepts",
      "url": "https://8bitconcepts.com"
    }},
    "publisher": {{
      "@type": "Organization",
      "name": "8bitconcepts",
      "url": "https://8bitconcepts.com"
    }},
    "inLanguage": "en",
    "isAccessibleForFree": true,
    "about": "enterprise AI adoption"
  }}
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet" />
  <style>
{css}
  </style>
</head>
<body>
  <nav>
    <a class="nav-logo" href="https://8bitconcepts.com">8bit<span>concepts</span></a>
    <div class="nav-links">
      <a href="https://8bitconcepts.com/#research">Research</a>
      <a href="https://8bitconcepts.com/#services">Services</a>
      <a href="mailto:hello@8bitconcepts.com" class="nav-cta">Talk to us</a>
    </div>
  </nav>
  <div class="article-wrap">
    <div class="eyebrow">{topic['eyebrow']}</div>
    <h1>{topic['title']}</h1>
    <p class="subtitle">[subtitle]</p>
    <div class="meta">
      <span class="meta-date">{month_year}</span>
      <span class="meta-tag">{topic['tag']}</span>
      <span class="meta-read">~X,XXX words</span>
    </div>
    <div class="article-body">
      [FULL ARTICLE BODY HERE with h2, h3, p, stat-row, callout, etc.]
    </div>
    <div class="footnotes">
      <h4>Sources</h4>
      <ol>[numbered sources with links]</ol>
    </div>
    <div class="related">
      <div class="related-label">Related Research</div>
      <div class="related-grid">
{related_html}
      </div>
    </div>
    <div class="article-cta">
      <p>Want help building AI measurement and evaluation infrastructure for your team?</p>
      <a href="mailto:hello@8bitconcepts.com">Talk to us</a>
    </div>
  </div>
  <footer>
    &copy; 2026 8bitconcepts &mdash; <a href="https://8bitconcepts.com">8bitconcepts.com</a>
  </footer>
</body>
</html>

Return ONLY the HTML. No markdown, no code fences, no explanation."""

    # Use opus for the highest quality writing
    result = call_claude(
        [{"role": "user", "content": prompt}],
        max_tokens=16384,
        model="claude-sonnet-4-6",  # Sonnet for cost efficiency on routine generation
    )

    # Clean up any markdown fences
    result = re.sub(r"^```html\s*", "", result.strip())
    result = re.sub(r"\s*```$", "", result.strip())

    return result


def update_index_html(topic):
    """Add a new research card to index.html."""
    with open(INDEX_HTML) as f:
        content = f.read()

    new_card = f'''      <a class="research-card" href="/research/{topic['slug']}.html">
        <div class="research-card-tag">{topic['tag']}</div>
        <div class="research-card-title">{topic['title']}</div>
        <div class="research-card-desc">{topic['subtitle'][:200]}</div>
      </a>'''

    # Insert before the closing </div> of research-grid
    # Find the last research-card and insert after it
    last_card_end = content.rfind("</a>\n    </div>\n  </div>\n\n  <!-- DIAGNOSTIC")
    if last_card_end == -1:
        # Try alternate pattern
        last_card_end = content.rfind("</a>\n    </div>")

    if last_card_end != -1:
        # Find the position right after the last </a> before </div> (research-grid close)
        insert_pos = content.rfind("</a>", 0, last_card_end + 4) + 4
        content = content[:insert_pos] + "\n" + new_card + content[insert_pos:]
        with open(INDEX_HTML, "w") as f:
            f.write(content)
        print(f"  Updated index.html with new research card")
    else:
        print(f"  WARNING: Could not find insertion point in index.html", file=sys.stderr)


def update_sitemap(topic):
    """Add new paper to sitemap.xml."""
    sitemap_path = SCRIPT_DIR / "sitemap.xml"
    if not sitemap_path.exists():
        return
    with open(sitemap_path) as f:
        content = f.read()
    new_entry = f"""  <url>
    <loc>https://8bitconcepts.com/research/{topic['slug']}.html</loc>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>"""
    content = content.replace("</urlset>", f"{new_entry}\n</urlset>")
    with open(sitemap_path, "w") as f:
        f.write(content)
    print(f"  Updated sitemap.xml")


def update_llms_txt(topic):
    """Add new paper to llms.txt."""
    llms_path = SCRIPT_DIR / "llms.txt"
    if not llms_path.exists():
        return
    with open(llms_path) as f:
        content = f.read()
    desc = topic.get("subtitle", topic.get("thesis", ""))[:100]
    new_line = f"- [{topic['title']}](https://8bitconcepts.com/research/{topic['slug']}.html): {desc}"
    # Insert before ## Contact
    content = content.replace("\n## Contact", f"\n{new_line}\n\n## Contact")
    with open(llms_path, "w") as f:
        f.write(content)
    print(f"  Updated llms.txt")


def update_feed_xml(topic, research_data):
    """Regenerate feed.xml from research.json so the new paper shows up at the top."""
    import datetime, json as _json
    feed_path = SCRIPT_DIR / "feed.xml"
    json_path = SCRIPT_DIR / "research.json"
    if not json_path.exists():
        return
    with open(json_path) as f:
        d = _json.load(f)
    papers = d.get("papers", [])
    now = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        '<channel>',
        '<title>8bitconcepts Research</title>',
        '<link>https://8bitconcepts.com/</link>',
        '<atom:link href="https://8bitconcepts.com/feed.xml" rel="self" type="application/rss+xml" />',
        '<description>Independent research on enterprise AI strategy, governance, and operational risk.</description>',
        '<language>en-us</language>',
        f'<lastBuildDate>{now}</lastBuildDate>',
        '<managingEditor>hello@8bitconcepts.com (8bitconcepts)</managingEditor>',
    ]
    for p in reversed(papers):  # newest-first
        cats = "".join(f"<category>{t}</category>" for t in p.get("tags", []))
        lines.append(
            f'<item><title>{p["title"]}</title><link>{p["url"]}</link><guid>{p["url"]}</guid>'
            f'<pubDate>{now}</pubDate><description><![CDATA[{p["summary"]}]]></description>{cats}</item>'
        )
    lines.append("</channel></rss>")
    with open(feed_path, "w") as f:
        f.write("\n".join(lines))
    print(f"  Updated feed.xml ({len(papers)} items)")


def git_commit_and_push(topic):
    """Commit new paper and push to deploy."""
    os.chdir(SCRIPT_DIR)
    slug = topic["slug"]
    subprocess.run(["git", "add", f"research/{slug}.html", "index.html",
                    "research/.topics-generated.json", "sitemap.xml", "llms.txt",
                    "feed.xml", "research.json"],
                    capture_output=True)
    subprocess.run(["git", "commit", "-m",
                    f"research: {topic['title']}\n\nAutonomously generated research paper.\n\nCo-Authored-By: Claude <noreply@anthropic.com>"],
                    capture_output=True)
    result = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  Pushed to origin/main — deploying to 8bitconcepts.com")
    else:
        print(f"  Git push failed: {result.stderr[:200]}", file=sys.stderr)


def cmd_generate(args):
    """Generate a new research paper."""
    print("=== 8bitconcepts Research Pipeline ===\n")

    # 1. Generate or use provided topic
    if args.topic:
        print(f"1. Using provided topic: {args.topic}")
        # Generate topic structure from provided text
        topic = json.loads(call_claude([{"role": "user", "content": f"""Generate a topic structure for a research paper about: {args.topic}

Return JSON only:
{{
  "title": "The Paper Title",
  "slug": "the-paper-slug",
  "tag": "Category Tag",
  "eyebrow": "Research — Category",
  "subtitle": "Hook paragraph",
  "thesis": "Core argument",
  "key_data_points": ["point 1", "point 2"],
  "search_queries": ["query 1", "query 2", "query 3"]
}}"""}]))
    else:
        print("1. Generating topic...")
        topic = generate_topic()

    print(f"   Title: {topic['title']}")
    print(f"   Tag: {topic['tag']}")
    print(f"   Thesis: {topic['thesis'][:150]}...")

    # Check for duplicates
    slug = topic["slug"]
    paper_path = RESEARCH_DIR / f"{slug}.html"
    if paper_path.exists():
        print(f"\n   Paper already exists at {paper_path}. Skipping.")
        return

    # 2. Research
    print("\n2. Researching topic...")
    research_data = research_topic(topic)
    print(f"   Gathered {len(research_data)} sources")

    # 3. Write paper
    print("\n3. Writing paper...")
    html = write_paper(topic, research_data)
    print(f"   Generated {len(html)} chars of HTML")

    if args.dry_run:
        print(f"\n   [DRY RUN] Would save to: {paper_path}")
        print(f"   First 500 chars:\n{html[:500]}")
        return

    # 4. Save paper
    print(f"\n4. Saving to {paper_path}")
    with open(paper_path, "w") as f:
        f.write(html)

    # 5. Update index.html, sitemap, llms.txt, feed.xml
    print("\n5. Updating index.html...")
    update_index_html(topic)
    update_sitemap(topic)
    update_llms_txt(topic)
    update_feed_xml(topic, research_data)

    # 6. Log topic
    log = load_topics_log()
    log.append({
        "title": topic["title"],
        "slug": slug,
        "tag": topic["tag"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })
    save_topics_log(log)

    # 7. Git commit and push
    if not args.no_push:
        print("\n6. Committing and pushing...")
        git_commit_and_push(topic)

    print(f"\n=== Done! Paper live at https://8bitconcepts.com/research/{slug}.html ===")


def cmd_list_topics(args):
    """List potential topics."""
    existing = get_existing_topics()
    print("Existing papers:")
    for t in existing:
        print(f"  - {t}")

    print("\nGenerating new topic ideas...")
    for i in range(3):
        topic = generate_topic()
        print(f"\n  {i+1}. {topic['title']}")
        print(f"     Tag: {topic['tag']}")
        print(f"     Thesis: {topic['thesis'][:120]}...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="8bitconcepts research paper pipeline")
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate a new research paper")
    gen.add_argument("--topic", help="Specific topic (otherwise auto-generated)")
    gen.add_argument("--dry-run", action="store_true", help="Preview without saving")
    gen.add_argument("--no-push", action="store_true", help="Don't git push after saving")

    sub.add_parser("list-topics", help="List potential new topics")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmds = {
        "generate": cmd_generate,
        "list-topics": cmd_list_topics,
    }
    cmds[args.command](args)
