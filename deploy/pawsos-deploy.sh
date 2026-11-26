#!/usr/bin/env bash
# Put one commit of main live on the server. GitHub Actions calls this after the tests pass
# (.github/workflows/deploy.yml); a person can run it too:  sudo pawsos-deploy <40-character sha>
#
# It updates two things, both built only from GitHub's main branch:
#   /opt/pawsos-site            the app behind /dashboard (pawsos-site.service, port 8041, demo data)
#   /var/www/pawsos-site        the website files Caddy serves on / and /demo
# It never touches /opt/pawsos (pawsos.service: the Telegram bot and the sandbox).
#
# Installed as /usr/local/bin/pawsos-deploy, owned by root. The deploy SSH key can run only
# this, and only with a commit id (see deploy/README.md).
set -euo pipefail

SHA="${1:-}"
APP=/opt/pawsos-site
WEB=/var/www/pawsos-site
SERVICE=pawsos-site
HEALTH=http://127.0.0.1:8041/health
LOG=/var/log/pawsos-deploy.log

# Only a full commit id is accepted: nothing else from the caller reaches a shell.
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "usage: pawsos-deploy <40-character commit sha>" >&2; exit 2; }

cd "$APP"   # the app's user must be able to read the working folder (pip looks at it)
exec > >(tee -a "$LOG") 2>&1
exec 9>/run/pawsos-deploy.lock
flock -n 9 || { echo "another deploy is running"; exit 75; }
echo "=== $(date -u +%FT%TZ) deploy $SHA"

as_app() { sudo -u pawsos -H "$@"; }
healthy() {
  for _ in $(seq 1 30); do
    curl -fsS -o /dev/null "$HEALTH" 2>/dev/null && curl -fsS -o /dev/null http://127.0.0.1:8041/dashboard 2>/dev/null && return 0
    sleep 1
  done
  return 1
}
install_and_restart() {
  as_app "$APP/.venv/bin/pip" install -q -e "$APP"
  systemctl restart "$SERVICE"   # its ExecStartPre runs: alembic upgrade head
}

PREV=$(as_app git -C "$APP" rev-parse HEAD)
as_app git -C "$APP" fetch -q origin main
# Deploy only commits that are on main, so a stray id cannot put unreviewed code live.
as_app git -C "$APP" merge-base --is-ancestor "$SHA" origin/main \
  || { echo "refusing: $SHA is not on main"; exit 3; }
if [[ "$PREV" == "$SHA" ]]; then echo "already live"; fi

as_app git -C "$APP" checkout -q -f "$SHA"
install_and_restart
if ! healthy; then
  echo "health check failed: going back to $PREV"
  as_app git -C "$APP" checkout -q -f "$PREV"
  install_and_restart
  healthy && echo "rolled back to $PREV" || echo "ROLLBACK ALSO UNHEALTHY: look at journalctl -u $SERVICE"
  exit 1
fi

# The app is healthy: swap in the website files from the same commit, all at once.
# The film MP4 is not in git (it is large), so carry the live one across.
NEW="$WEB.new"
rm -rf "$NEW" && mkdir -p "$NEW/static"
cp -a "$APP/app/static/site" "$NEW/static/site"
if [[ -f "$WEB/static/site/film/PawSOS_Goa_demo.mp4" && ! -f "$NEW/static/site/film/PawSOS_Goa_demo.mp4" ]]; then
  cp -a "$WEB/static/site/film/PawSOS_Goa_demo.mp4" "$NEW/static/site/film/"
fi
chown -R root:root "$NEW" && chmod -R a+rX "$NEW"
rm -rf "$WEB.prev"
mv "$WEB" "$WEB.prev" && mv "$NEW" "$WEB"   # the previous files stay in $WEB.prev for a quick manual undo

echo "live: $SHA (was $PREV)"
