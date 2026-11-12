#!/usr/bin/env bash
#
# One-command setup for an always-on Reddit pick-alerts watcher on a Linux VM
# (Ubuntu / Debian, e.g. an Oracle Cloud Always Free instance).
#
# Usage, from inside the cloned repo:
#     bash deploy/setup_vm.sh
#
# It installs dependencies, asks for your Telegram token + chat id (stored only
# on this VM), and runs the watcher as a systemd service that starts on boot and
# restarts if it ever crashes. Re-running it is safe (idempotent).
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="$(whoami)"
SERVICE="reddit-pick-alerts"
PY="$REPO_DIR/.venv/bin/python"
ENV_FILE="$REPO_DIR/.env"

echo "==> Repo:  $REPO_DIR"
echo "==> User:  $RUN_USER"

# --- system packages (git + python venv) ---------------------------------
if ! command -v git >/dev/null 2>&1 || ! python3 -c 'import venv' >/dev/null 2>&1; then
  echo "==> Installing git + python venv (needs sudo)..."
  sudo apt-get update -y
  sudo apt-get install -y git python3-venv python3-pip
fi

# --- python virtualenv + dependencies ------------------------------------
echo "==> Creating virtualenv and installing dependencies..."
python3 -m venv "$REPO_DIR/.venv"
"$REPO_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$REPO_DIR/.venv/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"

# --- secrets (.env, never committed) -------------------------------------
if [ ! -f "$ENV_FILE" ] || ! grep -q TELEGRAM_BOT_TOKEN "$ENV_FILE"; then
  echo
  echo "==> Enter your Telegram details (saved only on this VM, in $ENV_FILE):"
  read -rp "    TELEGRAM_BOT_TOKEN: " TOKEN
  read -rp "    TELEGRAM_CHAT_ID:   " CHATID
  ( umask 177; printf 'TELEGRAM_BOT_TOKEN=%s\nTELEGRAM_CHAT_ID=%s\n' "$TOKEN" "$CHATID" > "$ENV_FILE" )
  chmod 600 "$ENV_FILE"
  echo "    Saved."
else
  echo "==> Using existing $ENV_FILE"
fi

# --- systemd service ------------------------------------------------------
echo "==> Installing systemd service '$SERVICE'..."
sudo tee /etc/systemd/system/$SERVICE.service >/dev/null <<UNIT
[Unit]
Description=Reddit betting-pick Telegram alerts (alert-only)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$REPO_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$PY main.py --config config.yaml
Restart=always
RestartSec=10
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE"
sleep 2

echo
echo "==> Done. Current status:"
sudo systemctl --no-pager --full status "$SERVICE" | head -n 10 || true
echo
echo "----------------------------------------------------------------------"
echo "It is now running 24/7 and will restart on crash or reboot."
echo
echo "  Watch live logs:   journalctl -u $SERVICE -f"
echo "  Restart it:        sudo systemctl restart $SERVICE"
echo "  Stop it:           sudo systemctl stop $SERVICE"
echo "  Send a test alert: $PY tools/send_test_alert.py --config config.yaml"
echo "----------------------------------------------------------------------"
