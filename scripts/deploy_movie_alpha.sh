#!/usr/bin/env bash
# Deploy the alpha movie to this box's nginx webroot. Run with sudo:
#
#   sudo scripts/deploy_movie_alpha.sh
#
# - player  → /var/www/conflux-atlas/   (served at /conflux-atlas/)
# - film    → /var/www/media/            (mov + mp4 + m4a, same shelf as
#                                          the ogre / mcp-learning-engine demos)
# - site    → /etc/nginx/sites-available/dylanmccapes-systems
#              (from ~/.nakatomi-secrets/nginx/, then nginx -t && reload)

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# resolve the invoking user's home even under sudo
HOME_DIR="$(getent passwd "${SUDO_USER:-$USER}" | cut -d: -f6)"
SITE_SRC="$HOME_DIR/.nakatomi-secrets/nginx/dylanmccapes-systems"
SITE_DST="/etc/nginx/sites-available/dylanmccapes-systems"

if [[ $EUID -ne 0 ]]; then
  echo "needs root (writes /var/www and /etc/nginx) — run with sudo" >&2
  exit 1
fi

echo "🗺️  player → /var/www/conflux-atlas/"
rsync -a --delete \
  --exclude 'film/' \
  "$REPO/movie-alpha/" /var/www/conflux-atlas/

echo "🎬 film → /var/www/media/"
install -m 0644 "$REPO"/movie-alpha/film/conflux-alpha.mov /var/www/media/
install -m 0644 "$REPO"/movie-alpha/film/conflux-alpha-narrated.mp4 /var/www/media/
install -m 0644 "$REPO"/movie-alpha/film/conflux-alpha-narration.m4a /var/www/media/

chown -R www-data:www-data /var/www/conflux-atlas /var/www/media

echo "⚙️  site file → $SITE_DST"
install -m 0644 "$SITE_SRC" "$SITE_DST"

nginx -t
systemctl reload nginx

echo
echo "✅ deployed. Smoke:"
for p in conflux-atlas/ conflux-atlas/data/atlas.json conflux-atlas/assets/world_frame.json media/conflux-alpha-narrated.mp4; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1/$p")
  echo "  /$p → $code"
done
