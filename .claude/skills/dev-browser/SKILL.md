---
name: dev-browser
description: Browser automation with persistent page state via the dev-browser CLI. Use when asked to navigate websites, fill forms, take screenshots, extract web data, test web apps, or automate browser workflows. Trigger phrases include "go to [url]", "click on", "fill out the form", "take a screenshot", "scrape", "test the website", or any browser interaction request.
---

# Dev Browser

[dev-browser](https://github.com/SawyerHood/dev-browser) controls Chromium with short, sandboxed
JavaScript scripts. Pages persist between calls, so navigate once, then inspect → act → verify.

## In Claude Code on the web

The SessionStart hook (`.claude/hooks/session-start.sh`) installs the CLI and starts the
pre-installed headless Chromium with CDP on `127.0.0.1:9222`. **Always attach with `--connect`**;
the daemon-managed browser (`--headless` without `--connect`) is unavailable because its Chromium
download is blocked by the network policy.

```bash
dev-browser --connect http://127.0.0.1:9222 <<'JS'
const page = await browser.getPage("main");
await page.goto("http://localhost:3000", { waitUntil: "domcontentloaded" });
console.log(await page.title());
console.log((await page.snapshotForAI()).full);
JS
```

If the connection fails, re-run the hook: `CLAUDE_CODE_REMOTE=true .claude/hooks/session-start.sh`.

Notes:
- Only hosts allowed by the environment's network policy load; others fail with
  `net::ERR_TUNNEL_CONNECTION_FAILED`. Local dev servers (`localhost`) always work.
- Prefer `{ waitUntil: "domcontentloaded" }`: pages whose subresources are blocked may never fire `load`.
- Scripts run in QuickJS, not Node: no `require`, `fs`, `process`, or `fetch`.
- Act on refs from `snapshotForAI()` with `page.getByRef("e12").click()`.
- Screenshots: `await saveScreenshot(await page.screenshot(), "name.png")` returns a path under
  `~/.dev-browser/tmp/`, which can be viewed with the Read tool.

Run `dev-browser --help` for the full API.
