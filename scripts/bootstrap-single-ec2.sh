#!/usr/bin/env bash
# Run ON the large EC2 (Ubuntu 22.04, t3.large+), from inside the cloned repo:  ./scripts/bootstrap-single-ec2.sh
# Installs Docker/kubectl/kind/Helm, creates the kind cluster, installs ArgoCD, applies the root app.
set -euxo pipefail
KIND_VERSION="${KIND_VERSION:-v0.27.0}"; NODE_VERSION="${NODE_VERSION:-v1.32.2}"
KUBECTL_VERSION="${KUBECTL_VERSION:-v1.32.2}"; HELM_VERSION="${HELM_VERSION:-v3.17.3}"
cd "$(dirname "$0")/.."

sudo apt-get update -y
sudo apt-get install -y ca-certificates curl git jq unzip make docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

sudo curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/$KUBECTL_VERSION/bin/linux/amd64/kubectl"
sudo curl -fsSLo /usr/local/bin/kind "https://kind.sigs.k8s.io/dl/$KIND_VERSION/kind-linux-amd64"
sudo chmod +x /usr/local/bin/kubectl /usr/local/bin/kind
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | DESIRED_VERSION="$HELM_VERSION" sudo -E bash

printf 'fs.inotify.max_user_watches=524288\nfs.inotify.max_user_instances=512\n' | sudo tee /etc/sysctl.d/99-kind.conf
sudo sysctl --system

cat > /tmp/kind-config.yaml <<'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraPortMappings:
      - { containerPort: 30080, hostPort: 30080, listenAddress: "127.0.0.1" }
      - { containerPort: 30030, hostPort: 30030, listenAddress: "127.0.0.1" }
      - { containerPort: 30090, hostPort: 30090, listenAddress: "127.0.0.1" }
      - { containerPort: 30081, hostPort: 30081, listenAddress: "127.0.0.1" }
      - { containerPort: 30800, hostPort: 30800, listenAddress: "127.0.0.1" }
  - role: worker
EOF

# `sg docker` so the new docker group applies without logging out
sg docker -c "kind create cluster --name ai-sre --image kindest/node:$NODE_VERSION --config /tmp/kind-config.yaml --wait 180s"
helm repo add argo https://argoproj.github.io/argo-helm && helm repo update
helm upgrade --install argocd argo/argo-cd -n argocd --create-namespace \
  --set dex.enabled=false --set notifications.enabled=false \
  --set server.service.type=NodePort --set server.service.nodePortHttp=30080 \
  --set-string 'configs.params.server\.insecure=true' --wait --timeout 10m
kubectl apply -f gitops/bootstrap/root-app.yaml

echo
echo "DONE. ArgoCD admin password:"
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
echo "Next: register the GitHub runner (README), run the ci workflow, create agent secret."
