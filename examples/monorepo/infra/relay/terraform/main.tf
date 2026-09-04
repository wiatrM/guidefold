# Relay root stack. Modules only; select the environment with -var-file=envs/<env>.tfvars
# and the backend with -backend-config=envs/<env>.backend.hcl.

terraform {
  required_version = ">= 1.9.0"

  backend "s3" {
    # bucket, key, region and dynamodb_table come from envs/<env>.backend.hcl
    encrypt = true
  }

  required_providers {
    aws        = { source = "hashicorp/aws", version = "~> 5.60" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.31" }
  }
}

provider "aws" {
  region = var.region
  default_tags { tags = local.tags }
}

locals {
  name_prefix = "${var.project}-${var.env}"
  tags = {
    owner      = "relay-infra"
    env        = var.env
    component  = "relay"
    managed-by = "terraform"
  }
}

data "terraform_remote_state" "network" {
  backend = "s3"
  config  = { bucket = var.state_bucket, key = "${var.env}/network.tfstate", region = var.region }
}

module "cluster" {
  source = "./modules/cluster"

  name_prefix        = local.name_prefix
  kubernetes_version = var.kubernetes_version
  subnet_ids         = data.terraform_remote_state.network.outputs.private_subnet_ids
  node_pools         = var.node_pools
  tags               = local.tags
}
