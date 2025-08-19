#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="${here%/systemd}"

sudo install -d -m 0755 /etc/llamacpp
sudo install -Dm644 "$here/llamacpp.env" /etc/llamacpp/llamacpp.env
sudo install -Dm644 "$here/llamacpp.service" /etc/systemd/system/llamacpp.service

sudo systemctl daemon-reload
sudo systemctl enable --now llamacpp.service
sudo systemctl --no-pager status llamacpp.service || true

echo
echo "Tip: edit /etc/llamacpp/llamacpp.env and run: sudo systemctl restart llamacpp"
