# Most MCP Claims Still Do Not Complete A Live Handshake

Source paper: https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html
Drafted for native X Articles on 2026-04-29. Status: local draft only. Publishing requires action-time confirmation.

Most MCP discovery signals are still not working endpoints.

The current Not Human Search digest has 7,117 agent-ready sites in the MCP research crawl. 5,104 publish llms.txt. 418 pass a live MCP handshake. That is 5.9%.

The distinction matters because static directories usually count a mention, manifest, or discovery file. Agents do not run on mentions. They run on calls that complete.

A useful MCP check has to do more than grep a page for `mcp`:

1. Find the declared endpoint.
2. Open the connection.
3. Send a JSON-RPC initialize request.
4. Confirm a valid protocolVersion response.
5. Treat failures as operational failures, not as partial wins.

The gap is not proof that every unverified site is pretending. It can mean stale docs, auth walls, wrong paths, broken reverse proxies, scanner false positives, or endpoints that only work under a specific client. For an autonomous agent, the distinction is academic. The call still fails.

That is the current shape of the agentic web: context files are spreading quickly; working programmatic surfaces are spreading more slowly; live MCP endpoints are the narrowest part of the funnel.

The best sites are boring in the right way. They publish llms.txt, OpenAPI, ai-plugin metadata, structured API responses, AI-friendly robots rules, Schema.org, and an MCP endpoint that answers initialize.

That is the difference between agent-visible and agent-usable.

Original research and live methodology: https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html
