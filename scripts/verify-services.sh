#!/bin/bash
echo "=== Homelab LLM Stack Status ==="
for service in llamacpp ollama; do
    systemctl is-active --quiet $service && echo "✓ $service" || echo "✗ $service"
done

echo -e "\n=== Port Listeners ==="
ss -tlpn | grep -E ":(8001|8010|8080)" | awk '{print $4}' | sed 's/.*:/Port /'

echo -e "\n=== Model Storage ==="
df -h /mnt/nvme | tail -1 | awk '{print "NVMe: "$4" free of "$2}'
ls -1 /mnt/nvme/models/ 2>/dev/null | wc -l | xargs echo "Models deployed:"
