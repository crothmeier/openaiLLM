# Installation Commands for llama.cpp Service with Port Guard

Run these commands to install the service with port guard protection:

```bash
# 1. Install the port check guard script
sudo install -m 0755 -D check_port_free.sh /usr/local/lib/openaiLLM/check_port_free.sh

# 2. Verify the guard script works
/usr/local/lib/openaiLLM/check_port_free.sh 8010  # Should succeed
/usr/local/lib/openaiLLM/check_port_free.sh 8080  # Should fail (Open WebUI)

# 3. Install the complete service (includes port guard)
sudo ./install_service.sh

# OR manually:
sudo id llama >/dev/null 2>&1 || sudo useradd --system --home /srv/llama --shell /usr/sbin/nologin llama
sudo mkdir -p /srv/llama /var/log/openaiLLM /usr/local/lib/openaiLLM
sudo install -m 0755 -D build/bin/llama-server /srv/llama/llama-server
sudo install -m 0755 -D check_port_free.sh /usr/local/lib/openaiLLM/check_port_free.sh
sudo chown -R llama:llama /srv/llama /var/log/openaiLLM
sudo cp llamacpp-env.conf /etc/default/llamacpp
sudo cp llamacpp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable llamacpp.service

# 4. Verify the ExecStartPre line was added
grep ExecStartPre /etc/systemd/system/llamacpp.service

# 5. Test the port guard by temporarily occupying port 8010
# Terminal 1:
python3 -m http.server 8010

# Terminal 2:
sudo systemctl start llamacpp.service
sudo systemctl status llamacpp.service  # Should show failure due to port conflict

# Kill the python server in Terminal 1, then:
sudo systemctl start llamacpp.service
sudo systemctl status llamacpp.service  # Should start successfully (if model exists)
```

## Port Guard Features

The service now includes a preflight check that:
- Runs before the main service starts (`ExecStartPre`)
- Checks if the configured port (`${LLAMA_PORT}`) is free
- Prevents service startup if port is already in use
- Provides clear error message in logs

## Files Created

1. **check_port_free.sh** - Port availability checker script
2. **llamacpp.service** - Updated with `ExecStartPre` directive
3. **install_service.sh** - Installs both service and guard script

## Verification

After installation:
```bash
# Check the ExecStartPre line exists
grep ExecStartPre /etc/systemd/system/llamacpp.service
# Output: ExecStartPre=/usr/local/lib/openaiLLM/check_port_free.sh ${LLAMA_PORT}

# Check service status
sudo systemctl status llamacpp.service --no-pager
```