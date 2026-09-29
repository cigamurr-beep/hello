# hello

## Browser automation with dev-browser

This repo is set up so Claude Code on the web can drive a real browser with
[dev-browser](https://github.com/SawyerHood/dev-browser).

- `.claude/hooks/session-start.sh` runs at session start (cloud sessions only). It:
  1. installs `dev-browser@0.2.9` from npm and its daemon runtime (Playwright + QuickJS),
  2. trusts the sandbox's TLS-inspection CAs in Chromium's NSS store so HTTPS pages load,
  3. starts the pre-installed headless Chromium with remote debugging on `127.0.0.1:9222`.
- `.claude/skills/dev-browser/SKILL.md` tells Claude how to use it.

```bash
dev-browser --connect http://127.0.0.1:9222 <<'JS'
const page = await browser.getPage("main");
await page.goto("https://pypi.org/project/requests/", { waitUntil: "domcontentloaded" });
console.log(await page.title());
JS
```

dev-browser's own Chromium download (`dev-browser install`) is blocked by the cloud network policy,
which is why the hook uses `--connect` against the pre-installed browser. Only hosts allowed by the
environment's network policy will load.

To skip permission prompts for dev-browser, add `"Bash(dev-browser *)"` to `permissions.allow` in
`.claude/settings.json`. This lets any dev-browser script run without asking, so only do it if you
trust the scripts being run.
