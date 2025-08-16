#!/bin/bash
# cleanup-repo.sh

# 1. Create archive structure
mkdir -p archive/experimental/{gpt-oss,reflection-tests,old-scripts}
mkdir -p archive/kubernetes/old-manifests
mkdir -p docs/archive

# 2. Move experimental/test files (won't break production)
git mv gpt-oss-20b*.* fetch-gpt-oss.sh test-gpt-oss.sh archive/experimental/gpt-oss/
git mv recursive_self_reflection_test.py test_reflection_demo.py archive/experimental/reflection-tests/
git mv requirements_reflection.txt archive/experimental/reflection-tests/

# 3. Consolidate duplicate K8s manifests
git mv k8s/overlays k8s/base/monitoring archive/kubernetes/old-manifests/
# Keep only k8s/hardened as the production version

# 4. Archive redundant scripts
git mv nvme-model-storage/*compat.sh archive/experimental/old-scripts/
git mv ollama-startup.sh ollama-shutdown.sh archive/experimental/old-scripts/

git commit -m "chore: archive experimental and redundant code"
