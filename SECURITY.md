# Security Policy — 8bitconcepts

## Scope Note

8bitconcepts.com is a **static site hosted on GitHub Pages**. There's no runtime server, no database, no user accounts, and no authentication. Most classes of server-side vulnerability don't apply. What can go wrong:

- Client-side JavaScript bugs (XSS via untrusted content in a published page, CSP weaknesses).
- Broken third-party embeds (if a partner site is compromised).
- Supply-chain issues in our static generators (the research-paper pipeline).
- Outreach forms — but those POST to `aidevboard.com/api/v1/lead` and `aidevboard.com/api/v1/subscribe`. Bugs in those handlers are scoped to the **AI Dev Jobs** [SECURITY.md](https://github.com/unitedideas/ai-dev-jobs/blob/main/SECURITY.md), not here.

## Reporting a Vulnerability

- **Email** (preferred for sensitive reports): security@8bitconcepts.com
- **GitHub issues**: https://github.com/unitedideas/8bitconcepts/issues (for lower-severity issues where public discussion is fine)
- **Mirrored contact list**: https://8bitconcepts.com/.well-known/security.txt

Please include:

1. The exact page (URL + section) where the issue manifests.
2. Browser + OS (for client-side issues).
3. Impact — what can an attacker do?
4. A reproducible test case or screenshot.

## Response Commitment

- **Acknowledgement**: within **3 business days** of receiving a report.
- **Fix**: target **14 days** for anything that affects the live site — pushing static HTML is fast, so we aim to ship faster than the server products.
- **Disclosure**: coordinated. Default **30-day embargo** from the fix being deployed.

## Scope

In scope:

- The live site at `8bitconcepts.com`.
- The `/research/*` pages and their metadata.
- The `/.well-known/*` files.
- The llms.txt, sitemap.xml, feed.xml.
- Any form that submits to a `8bitconcepts.com` URL (currently: none — all forms target aidevboard.com).
- The MCP preview manifest at `/.well-known/mcp.json` (the real JSON-RPC endpoint isn't implemented yet; manifest says `status: preview`).

Out of scope:

- `*.github.io` — infrastructure provider.
- Backend handlers at `aidevboard.com` or `nothumansearch.ai` — see their respective `SECURITY.md` files.
- Stale research-paper numbers (data-drift isn't a security issue).
- Issues that require physical access to your own device.

## Safe Harbor

Good-faith research is welcomed. I will not pursue legal action for research that operates within scope, doesn't degrade service for others, doesn't access / modify / destroy data belonging to others, and reports via the channels above before public disclosure.

## What I Cannot Offer

- A formal bug bounty (no paid tier for reports yet).
- SLA in hours — solo operator.
- NDA / exclusivity agreements.

Clear reports get public credit unless you ask to stay anonymous.
