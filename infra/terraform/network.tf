# Network for the private RDS + App Runner egress.
#
# Why this exists: App Runner reaches a *private* RDS through a VPC
# connector. The catch — attaching a VPC connector routes ALL of App
# Runner's outbound traffic through this VPC. So the app can no longer
# reach Bedrock / Cognito / S3 over the public internet. We give it back
# those paths with VPC endpoints instead of a NAT gateway (a NAT is
# ~$32/mo; the two interface endpoints below are ~$7.30/mo each).
#
# COST CHOICE: the VPC connector and both interface endpoints are pinned
# to a SINGLE AZ (subnet index 0). Interface endpoints bill per-AZ, so
# one AZ ~halves their cost at the price of cross-AZ redundancy — an
# acceptable trade for a single-user app. The DB subnet group still
# spans two AZs because RDS *requires* it, but the instance itself is
# pinned to the same AZ as the connector to avoid cross-AZ data charges.

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs        = slice(data.aws_availability_zones.available.names, 0, 2)
  az_primary = local.azs[0]
  vpc_cidr   = "10.0.0.0/16"
}

resource "aws_vpc" "main" {
  cidr_block           = local.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.project_name}-vpc" }
}

# Two private subnets (no IGW, no public IPs). Egress is only via the
# VPC endpoints below — there is intentionally no route to the internet.
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(local.vpc_cidr, 8, count.index)
  availability_zone = local.azs[count.index]
  tags              = { Name = "${var.project_name}-private-${count.index}" }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.project_name}-private" }
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# ── Security groups ────────────────────────────────────────────────────
# The App Runner connector ENIs. No ingress (nothing connects *to* the
# app inside the VPC — the public URL is fronted by App Runner itself).
resource "aws_security_group" "connector" {
  name_prefix = "${var.project_name}-connector-"
  description = "App Runner VPC connector ENIs"
  vpc_id      = aws_vpc.main.id

  egress {
    description = "All outbound (scoped by the destination SGs/endpoints)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle { create_before_destroy = true }
}

# Interface VPC endpoints (Bedrock, Cognito). Only the connector may
# reach them on 443.
resource "aws_security_group" "endpoints" {
  name_prefix = "${var.project_name}-endpoints-"
  description = "Interface VPC endpoints"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "HTTPS from the App Runner connector"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.connector.id]
  }

  lifecycle { create_before_destroy = true }
}

# RDS. Reachable from the connector always; from admin_cidr only when
# the DB is toggled public for an initial data load (see rds.tf).
resource "aws_security_group" "rds" {
  name_prefix = "${var.project_name}-rds-"
  description = "Postgres access"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Postgres from the App Runner connector"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.connector.id]
  }

  # Admin/ingest access from a single operator IP, only if set.
  dynamic "ingress" {
    for_each = var.admin_cidr == "" ? [] : [var.admin_cidr]
    content {
      description = "Postgres from operator (ingest/migrations)"
      from_port   = 5432
      to_port     = 5432
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle { create_before_destroy = true }
}

# ── VPC endpoints ──────────────────────────────────────────────────────
# S3: gateway endpoint — FREE. Routed via the private route table.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]
  tags              = { Name = "${var.project_name}-s3" }
}

# Bedrock model invocation (chat + embeddings). Interface endpoint,
# single AZ. private_dns_enabled lets the app keep using the normal
# bedrock-runtime.<region>.amazonaws.com hostname.
resource "aws_vpc_endpoint" "bedrock_runtime" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private[0].id]
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = true
  tags                = { Name = "${var.project_name}-bedrock-runtime" }
}

# Cognito IDP — the API verifies JWTs and fetches the pool's JWKS from
# cognito-idp.<region>.amazonaws.com. Without this (and with no internet
# egress) JWT verification would fail.
resource "aws_vpc_endpoint" "cognito_idp" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.cognito-idp"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private[0].id]
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = true
  tags                = { Name = "${var.project_name}-cognito-idp" }
}

# Secrets Manager — the container fetches the RDS-managed DB password here
# at connect time (rotation-safe). Required because the VPC connector
# routes all egress through the VPC; without it the app couldn't reach
# Secrets Manager. ~$7.30/mo (single-AZ).
resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private[0].id]
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = true
  tags                = { Name = "${var.project_name}-secretsmanager" }
}

# ── App Runner VPC connector ───────────────────────────────────────────
# Pinned to a single subnet/AZ so it always lands beside the interface
# endpoints above (which are single-AZ for cost). Changing subnets or
# SGs forces a new connector — App Runner treats it as immutable.
resource "aws_apprunner_vpc_connector" "this" {
  vpc_connector_name = "${var.project_name}-vpc"
  subnets            = [aws_subnet.private[0].id]
  security_groups    = [aws_security_group.connector.id]
}
