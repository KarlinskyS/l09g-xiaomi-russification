#!/usr/bin/env bash
# Русификация колонки одной командой:  ./tools/russify-speaker.sh <speaker-ip> [locale]
# Поднимает venv (glocaltokens+gpsoauth) при первом запуске, затем гонит russify_speaker.py.
# Нужен: adb с подключённым рутованным телефоном в той же Wi-Fi, что и колонка;
#        secrets/google-master-token.txt (master-token аккаунта-владельца).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/venv"

if [ ! -x "$VENV/bin/python" ]; then
  echo ">> первый запуск: создаю venv и ставлю glocaltokens+gpsoauth ..."
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q glocaltokens gpsoauth
fi

if [ $# -lt 1 ]; then
  echo "использование: $0 <speaker-ip> [locale=ru]"
  echo "IP колонки: открой её в приложении Google Home, либо просканируй сеть с телефона."
  exit 1
fi

exec "$VENV/bin/python" "$HERE/russify_speaker.py" "$@"
