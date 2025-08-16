#!/bin/bash
# Script to import Docker image to k3s containerd
# Requires sudo password

set -e

IMAGE="nvme-models:local"
TAR_FILE="/tmp/nvme-models.tar"

echo "Saving Docker image ${IMAGE} to ${TAR_FILE}..."
docker save ${IMAGE} -o ${TAR_FILE}

echo "Importing image to k3s containerd (requires sudo)..."
sudo k3s ctr images import ${TAR_FILE}

echo "Cleaning up..."
rm -f ${TAR_FILE}

echo "Verifying image in k3s..."
sudo k3s ctr images ls | grep nvme-models || echo "Image not found in k3s containerd"

echo "Done!"