#!/bin/bash
# Sets up dev-browser (https://github.com/SawyerHood/dev-browser) for Claude Code on the web.
#
# The cloud network policy blocks dev-browser's own Chromium download, so instead we
# launch the pre-installed Playwright Chromium with a CDP port and attach to it:
#
#   dev-browser --connect http://127.0.0.1:9222 <<'JS' ... JS
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

DEV_BROWSER_VERSION="0.2.9"
CDP_PORT="${DEV_BROWSER_CDP_PORT:-9222}"
PROFILE_DIR="$HOME/.dev-browser/chrome-profile"
LOG_FILE="$HOME/.dev-browser/chrome.log"

log() { echo "[dev-browser setup] $*" >&2; }

# 1. CLI
if ! npm ls -g --depth=0 "dev-browser@$DEV_BROWSER_VERSION" >/dev/null 2>&1; then
  log "installing dev-browser@$DEV_BROWSER_VERSION"
  npm install -g "dev-browser@$DEV_BROWSER_VERSION" >/dev/null 2>&1
fi

# 2. Daemon runtime deps (playwright + quickjs in ~/.dev-browser/node_modules).
#    `dev-browser install` installs these, then tries to download Chromium, which
#    the network policy blocks — so a non-zero exit is expected and ignored.
if [ ! -d "$HOME/.dev-browser/node_modules/playwright-core" ]; then
  log "installing daemon runtime dependencies"
  dev-browser install >/dev/null 2>&1 || true
fi
if [ ! -d "$HOME/.dev-browser/node_modules/playwright-core" ]; then
  log "ERROR: daemon dependencies failed to install"
  exit 1
fi

# 3. Trust the sandbox's TLS-inspecting CAs in Chromium's NSS store so HTTPS pages load.
#    Proxied and direct connections are re-signed by different Anthropic CAs, all of
#    which are in the CA bundle; import each of them (Chromium ignores SSL_CERT_FILE).
CA_BUNDLE="/root/.ccr/ca-bundle.crt"
NSSDB="sql:$HOME/.pki/nssdb"
CA_CHANGED=0
if [ -f "$CA_BUNDLE" ]; then
  if ! command -v certutil >/dev/null 2>&1; then
    log "installing certutil (libnss3-tools)"
    { apt-get install -y libnss3-tools || { apt-get update && apt-get install -y libnss3-tools; }; } >/dev/null 2>&1 || true
  fi
  if command -v certutil >/dev/null 2>&1; then
    mkdir -p "$HOME/.pki/nssdb"
    [ -f "$HOME/.pki/nssdb/cert9.db" ] || certutil -N -d "$NSSDB" --empty-password
    CA_DIR="$(mktemp -d)"
    awk -v dir="$CA_DIR" '/BEGIN CERTIFICATE/{n++} n{print > (dir "/" n ".pem")}' "$CA_BUNDLE"
    for pem in "$CA_DIR"/*.pem; do
      subject="$(openssl x509 -in "$pem" -noout -subject -nameopt RFC2253 2>/dev/null || true)"
      case "$subject" in *O=Anthropic*) ;; *) continue ;; esac
      nick="ccr-$(openssl x509 -in "$pem" -noout -fingerprint -sha256 | tr -d ':' | cut -d= -f2 | cut -c1-16)"
      if ! certutil -L -d "$NSSDB" -n "$nick" >/dev/null 2>&1; then
        certutil -A -d "$NSSDB" -n "$nick" -t "C,," -i "$pem"
        CA_CHANGED=1
      fi
    done
    rm -rf "$CA_DIR"
  else
    log "WARNING: certutil unavailable; HTTPS pages will fail certificate checks"
  fi
fi

# 4. Headless Chromium with remote debugging
cdp_up() { curl -sf --noproxy '*' "http://127.0.0.1:$CDP_PORT/json/version" >/dev/null 2>&1; }

# Chromium reads NSS trust at startup, so restart it if new CAs were imported.
if [ "$CA_CHANGED" = 1 ] && cdp_up; then
  log "restarting Chromium to pick up new CA certificates"
  pkill -f -- "--remote-debugging-port=$CDP_PORT --user-data-dir=$PROFILE_DIR" || true
  for _ in $(seq 1 20); do cdp_up || break; sleep 0.25; done
fi

if ! cdp_up; then
  CHROME="${DEV_BROWSER_CHROME:-}"
  [ -n "$CHROME" ] || CHROME="$(ls /opt/pw-browsers/chromium 2>/dev/null || true)"
  [ -n "$CHROME" ] || CHROME="$(ls /opt/pw-browsers/chromium-*/chrome-linux*/chrome 2>/dev/null | sort -V | tail -1 || true)"
  if [ -z "$CHROME" ]; then
    log "ERROR: no Chromium binary found (set DEV_BROWSER_CHROME)"
    exit 1
  fi
  log "starting $CHROME on port $CDP_PORT"
  mkdir -p "$PROFILE_DIR"
  setsid nohup "$CHROME" \
    --headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage \
    --no-first-run --no-default-browser-check \
    --remote-debugging-address=127.0.0.1 --remote-debugging-port="$CDP_PORT" \
    --user-data-dir="$PROFILE_DIR" about:blank >"$LOG_FILE" 2>&1 < /dev/null &
  for _ in $(seq 1 40); do cdp_up && break; sleep 0.25; done
  if ! cdp_up; then
    log "ERROR: Chromium did not open CDP port $CDP_PORT (see $LOG_FILE)"
    exit 1
  fi
fi

if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export DEV_BROWSER_CDP_URL=http://127.0.0.1:$CDP_PORT" >> "$CLAUDE_ENV_FILE"
fi

log "ready: dev-browser --connect http://127.0.0.1:$CDP_PORT"
