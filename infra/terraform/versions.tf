terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Start with local state. Once it's working, migrate to S3 by
  # uncommenting and running `terraform init -migrate-state`:
  #
  # backend "s3" {
  #   bucket = "lawagent-tfstate-<account-id>"
  #   key    = "lawagent/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "lawagent"
      ManagedBy = "terraform"
    }
  }
}
