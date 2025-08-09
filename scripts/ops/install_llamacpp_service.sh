#!/bin/bash
# Quick install script to be run with sudo
set -e

echo "Installing llama.cpp service..."

# Create user if needed
id llama >/dev/null 2>&1 || useradd --system --home /srv/llama --shell /usr/sbin/nologin llama

# Create directories
mkdir -p /srv/llama /var/log/openaiLLM /usr/local/lib/openaiLLM

# Install binary and scripts
install -m 0755 -D build/bin/llama-server /srv/llama/llama-server
install -m 0755 -D check_port_free.sh /usr/local/lib/openaiLLM/check_port_free.sh

# Set permissions
chown -R llama:llama /srv/llama /var/log/openaiLLM

# Install config and service
cp llamacpp-env.conf /etc/default/llamacpp
cp llamacpp.service /etc/systemd/system/

# Reload and start
systemctl daemon-reload
systemctl enable llamacpp.service
systemctl start llamacpp.service

echo "Service installed and started!"
systemctl status llamacpp.service --no-pager