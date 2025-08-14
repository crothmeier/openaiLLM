KUSTOMIZE ?= kubectl kustomize

.PHONY: deploy delete diff logs verify metrics

deploy:
	kubectl apply -f overlays/prod/ns.yaml
	kubectl apply -k overlays/prod

delete:
	kubectl delete -k overlays/prod || true
	kubectl delete ns ai-infer --ignore-not-found
	kubectl delete -f base/storage/pv-nvme.yaml --ignore-not-found

diff:
	$(KUSTOMIZE) overlays/prod | kubectl diff -f - || true

logs:
	kubectl -n ai-infer logs -l app=vllm --all-containers=true --tail=200

verify:
	kubectl -n ai-infer exec deploy/vllm -c nvme-metrics -- \
	  curl -s localhost:9109/metrics | head -n 20 || true

metrics:
	kubectl -n gpu-operator get pods -l app.kubernetes.io/name=dcgm-exporter -o wide