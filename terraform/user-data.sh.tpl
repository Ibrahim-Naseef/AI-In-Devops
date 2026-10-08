#!/bin/bash
# Bootstraps: Docker, kubectl, kind, Helm -> kind cluster -> ArgoCD -> root app-of-apps
set -euxo pipefail
exec > >(tee -a /var/log/ai-sre-bootstrap.log) 2>&1
export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y ca-certificates curl git jq unzip docker.io
systemctl enable --now docker
usermod -aG docker ubuntu

curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/${kubectl_version}/bin/linux/amd64/kubectl"
curl -fsSLo /usr/local/bin/kind "https://kind.sigs.k8s.io/dl/${kind_version}/kind-linux-amd64"
chmod +x /usr/local/bin/kubectl /usr/local/bin/kind
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | DESIRED_VERSION=${helm_version} bash

# kind needs more inotify headroom
cat > /etc/sysctl.d/99-kind.conf <<'EOF'
fs.inotify.max_user_watches=524288
fs.inotify.max_user_instances=512
EOF
sysctl --system

# NodePorts are published on the host's loopback only; reach them through an SSH tunnel.
cat > /opt/kind-config.yaml <<'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraPortMappings:
      - { containerPort: 30080, hostPort: 30080, listenAddress: "127.0.0.1" } # ArgoCD
      - { containerPort: 30030, hostPort: 30030, listenAddress: "127.0.0.1" } # Grafana
      - { containerPort: 30090, hostPort: 30090, listenAddress: "127.0.0.1" } # Prometheus
      - { containerPort: 30081, hostPort: 30081, listenAddress: "127.0.0.1" } # demo app
      - { containerPort: 30800, hostPort: 30800, listenAddress: "127.0.0.1" } # AI SRE agent
  - role: worker
EOF

cat > /opt/bootstrap-user.sh <<'EOF'
#!/bin/bash
set -euxo pipefail
kind create cluster --name ai-sre --image kindest/node:${k8s_node_version} --config /opt/kind-config.yaml --wait 180s

helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
helm upgrade --install argocd argo/argo-cd -n argocd --create-namespace \
  --set dex.enabled=false --set notifications.enabled=false \
  --set server.service.type=NodePort --set server.service.nodePortHttp=30080 \
  --set-string 'configs.params.server\.insecure=true' \
  --wait --timeout 10m

git clone ${repo_url} "$HOME/ai-sre-gitops"
kubectl apply -f "$HOME/ai-sre-gitops/gitops/bootstrap/root-app.yaml"
EOF
chmod +x /opt/bootstrap-user.sh

runuser -l ubuntu -c /opt/bootstrap-user.sh
touch /var/lib/ai-sre-bootstrap.done
