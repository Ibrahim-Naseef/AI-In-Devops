#!/usr/bin/env bash
# Installs a GitHub Actions self-hosted runner on the EC2 box (as a systemd service).
# Needs either: `gh` CLI logged in (gh auth login)  OR  RUNNER_TOKEN=<token from repo Settings > Actions > Runners > New>
set -euo pipefail
cd "$(dirname "$0")/.."
KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
IP="$(terraform -chdir=terraform output -raw "${HOST_OUTPUT:-public_ip}")"
REPO="$(git config --get remote.origin.url | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')"
TOKEN="${RUNNER_TOKEN:-$(gh api -X POST "repos/$REPO/actions/runners/registration-token" --jq .token)}"
echo "Registering runner for $REPO on $IP ..."
ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "ubuntu@$IP" "REPO='$REPO' TOKEN='$TOKEN' bash -s" <<'EOF'
set -euo pipefail
mkdir -p ~/actions-runner && cd ~/actions-runner
V=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest | jq -r .tag_name | sed 's/^v//')
curl -fsSLo runner.tar.gz "https://github.com/actions/runner/releases/download/v$V/actions-runner-linux-x64-$V.tar.gz"
tar xzf runner.tar.gz
sudo ./bin/installdependencies.sh
./config.sh --unattended --url "https://github.com/$REPO" --token "$TOKEN" --name ec2-kind-runner --labels kind,ec2 --replace
sudo ./svc.sh install ubuntu
sudo ./svc.sh start
EOF
echo "Runner registered. Check: GitHub repo > Settings > Actions > Runners"
