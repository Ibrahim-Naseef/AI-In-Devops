terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Optional remote state (create the bucket + lock table first):
  # backend "s3" {
  #   bucket         = "your-tf-state-bucket"
  #   key            = "ai-sre-gitops/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "tf-locks"
  # }
}
