# Run everything from a control EC2 (no laptop needed)

```
You (browser) --ssh -J--> control EC2 --private IP--> kind-host EC2 (created by Terraform)
```

## 1. IAM role for the control box (once, in the AWS console)
IAM > Roles > Create role > trusted entity **EC2** > attach **AmazonEC2FullAccess** (demo; tighten later) > name `ai-sre-control`.

## 2. Launch the control EC2
Ubuntu 22.04, **t3.small** (or micro), 20 GB, default VPC, SSH allowed from your IP.
Advanced details > **IAM instance profile = ai-sre-control**.

## 3. Prepare the control box
```bash
ssh ubuntu@<control-public-ip>
sudo apt-get update && sudo apt-get install -y git make jq curl unzip gnupg lsb-release

# Terraform
wget -qO- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt-get update && sudo apt-get install -y terraform

# GitHub CLI
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list
sudo apt-get update && sudo apt-get install -y gh
gh auth login && gh auth setup-git

ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519     # key used for the kind-host
aws sts get-caller-identity 2>/dev/null || true       # Terraform uses the instance role automatically
```

## 4. Deploy
```bash
git clone https://github.com/<you>/ai-sre-gitops.git && cd ai-sre-gitops
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# allowed_ssh_cidr = "<control PRIVATE ip>/32"   (hostname -I | awk '{print $1}')
# repo_url = your repo URL
export HOST_OUTPUT=private_ip          # SSH to the kind-host over the VPC
make up && make wait
make runner && gh workflow run ci.yml
make secrets                           # after creating agent/.env
make break-oom                         # demos work as before
```
Keep `export HOST_OUTPUT=private_ip` in every new shell (or add it to `~/.bashrc`).

## 5. Open the UIs from your laptop (jump through the control box)
```bash
ssh -N -J ubuntu@<control-public-ip> \
  -L 8080:127.0.0.1:30080 -L 3000:127.0.0.1:30030 -L 9090:127.0.0.1:30090 \
  -L 8081:127.0.0.1:30081 -L 8800:127.0.0.1:30800 ubuntu@<kind-host-private-ip>
```
(`terraform -chdir=terraform output private_ip` shows the IP. `make tunnel` on the control box would only expose ports on the control box itself.)

## Notes
- Terraform state is a local file on the control box. If you destroy that box first you lose track of the kind-host: run `make down` first, or use the S3 backend block in `terraform/versions.tf`.
- Cleanup order: `make down` (kind-host), then terminate the control EC2.
- The instance role is more convenient than access keys, but anything on the control box can create EC2 resources. Keep it private.
