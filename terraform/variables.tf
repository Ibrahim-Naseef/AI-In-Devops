variable "region" {
  type    = string
  default = "us-east-1"
}

variable "name" {
  type    = string
  default = "ai-sre"
}

variable "instance_type" {
  description = "kind + ArgoCD + Prometheus/Grafana need ~8GB RAM. t3.large is the minimum; t3.xlarge is comfortable."
  type        = string
  default     = "t3.large"
}

variable "use_spot" {
  description = "Use a one-time Spot instance (cheaper, can be reclaimed)."
  type        = bool
  default     = false
}

variable "volume_size" {
  type    = number
  default = 40
}

variable "allowed_ssh_cidr" {
  description = "Your public IP in CIDR form, e.g. 203.0.113.7/32. Do NOT use 0.0.0.0/0."
  type        = string
}

variable "public_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519.pub"
}

variable "repo_url" {
  description = "HTTPS URL of YOUR copy of this repo (must be public so the EC2 box can clone it)."
  type        = string
}

variable "kind_version" {
  type    = string
  default = "v0.27.0"
}

variable "k8s_node_version" {
  description = "kindest/node tag; must exist for the chosen kind version."
  type        = string
  default     = "v1.32.2"
}

variable "kubectl_version" {
  type    = string
  default = "v1.32.2"
}

variable "helm_version" {
  type    = string
  default = "v3.17.3"
}
