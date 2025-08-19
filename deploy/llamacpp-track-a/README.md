# Track A — GPT-OSS-20B (MXFP4) with llama.cpp

This bundle includes:

- **systemd/**: drop-in unit + env to run llama-server on bare metal.
- **kubernetes/**: Kustomize base + L4 overlay (hostPath models, GPU scheduling).
- **PrometheusRule**: TPS SLO and optional TTFT p95 rule (requires TTFT exporter metric).

## Paths and defaults

- Model: `/mnt/nvme/models/gpt-oss-20b/gpt-oss-20b-mxfp4.gguf`
- Port: `8010`, Host: `127.0.0.1` (systemd) / `0.0.0.0` (K8s)
- Context: `8192`, GPU offload: `--n-gpu-layers 999`, Parallel slots: `-np 4`

## Install (systemd)

```bash
cd systemd
./install_systemd.sh
# edit /etc/llamacpp/llamacpp.env as needed, then:
sudo systemctl restart llamacpp
curl -sf http://127.0.0.1:8010/health && echo "ok"
curl -sf http://127.0.0.1:8010/v1/models | jq .
```

## Deploy (Kubernetes with Kustomize)

```bash
# Adjust overlays/l4/patch-deployment.yaml hostPath as needed
kubectl apply -k kubernetes/overlays/l4
kubectl -n ai-serving get pods -l app=gpt-oss20b-llamacpp
curl -sf http://$(kubectl -n ai-serving get svc gpt-oss20b-llamacpp -o jsonpath='{.spec.clusterIP}'):8010/health
```

## Metrics

- Enable `--metrics` (already set). Prometheus scrapes `/metrics` on the service.
- TPS = `sum(rate(llamacpp:tokens_predicted_total[5m]))`
- Prompt TPS = `sum(rate(llamacpp:prompt_tokens_total[5m]))`
- **TTFT**: llama.cpp doesn't expose a first-token histogram by default. Either:
  1) add a tiny sidecar that measures TTFT and emits `llamacpp:ttft_seconds_bucket`, or
  2) run a synthetic probe job (blackbox exporter) to measure TTFT.

## Notes

- Container image: `ghcr.io/ggml-org/llama.cpp:server-cuda-b4890` (adjust as you pin versions).
- Health endpoints: `/health`, `/v1/models`. OpenAI-compatible endpoints under `/v1`.
- Security: systemd unit binds to `127.0.0.1`; expose via your existing mesh / reverse proxy if needed.
