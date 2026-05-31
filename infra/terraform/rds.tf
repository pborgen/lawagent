# RDS PostgreSQL (pgvector) for the case vector store.
#
# Tier: db.t4g.micro, Single-AZ, 20 GB gp3 — the cheap baseline. pgvector
# ships with RDS PostgreSQL 15.2+/16; the schema runs `CREATE EXTENSION
# vector` (see packages/db). Storage is encrypted; SSL is enforced.
#
# RDS generates, stores, and auto-rotates the master password in AWS
# Secrets Manager (manage_master_user_password). The password never
# exists in tfvars or in Terraform state — only the secret ARN does. The
# App Runner container fetches it at connect time (see apprunner.tf +
# packages/db/session.py) so rotation is transparent.
#
# INGEST ACCESS: the instance is private (no public IP), so your laptop
# can't reach it to run migrations / ingest by default. For an initial
# load, set `db_publicly_accessible = true` and `admin_cidr` to your IP,
# `terraform apply`, then build a URL from the RDS-managed secret:
#   pw=$(aws secretsmanager get-secret-value --secret-id \
#       "$(terraform output -raw master_user_secret_arn)" \
#       --query SecretString --output text | jq -r .password)
#   export LAWAGENT_PG_URL="postgresql+psycopg://lawagent:$pw@$(terraform \
#       output -raw db_endpoint):5432/lawagent?sslmode=require"
# load the data, then flip both vars back and apply again.

variable "db_username" {
  description = "Master username for the Postgres instance."
  type        = string
  default     = "lawagent"
}

variable "db_name" {
  description = "Initial database name created on the instance."
  type        = string
  default     = "lawagent"
}

variable "db_engine_version" {
  description = "RDS PostgreSQL engine version. Must support pgvector (>= 15.2)."
  type        = string
  default     = "16.4"
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB (gp3)."
  type        = number
  default     = 20
}

variable "db_publicly_accessible" {
  description = "Temporarily expose the DB on a public endpoint for an initial ingest/migration from your laptop. Keep false in steady state."
  type        = bool
  default     = false
}

variable "admin_cidr" {
  description = "Operator IP CIDR (e.g. \"203.0.113.4/32\") allowed to reach Postgres for ingest/migrations. Only used when db_publicly_accessible = true. Empty = no operator ingress."
  type        = string
  default     = ""
}

# RDS requires a subnet group spanning >= 2 AZs even for a Single-AZ
# instance. The instance itself is pinned to az_primary (same AZ as the
# App Runner connector + interface endpoints) to avoid cross-AZ traffic.
resource "aws_db_subnet_group" "this" {
  name       = "${var.project_name}-db"
  subnet_ids = [for s in aws_subnet.private : s.id]
}

# Enforce TLS at the server. psycopg negotiates SSL by default, and the
# URL below also asks for sslmode=require.
resource "aws_db_parameter_group" "this" {
  name_prefix = "${var.project_name}-pg16-"
  family      = "postgres16"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  lifecycle { create_before_destroy = true }
}

resource "aws_db_instance" "this" {
  identifier     = "${var.project_name}-db"
  engine         = "postgres"
  engine_version = var.db_engine_version
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = 50 # let storage autoscale a little; still cheap
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  # RDS owns the master password: generated + auto-rotated in Secrets Manager.
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.this.name

  multi_az            = false
  availability_zone   = local.az_primary
  publicly_accessible = var.db_publicly_accessible

  backup_retention_period    = 7
  auto_minor_version_upgrade = true

  # Portfolio/dev posture: let `terraform destroy` work cleanly. Flip
  # deletion_protection on and drop skip_final_snapshot for anything
  # you actually care about keeping.
  deletion_protection = false
  skip_final_snapshot = true
  apply_immediately   = true
}

output "db_endpoint" {
  description = "RDS endpoint host (no port). For ad-hoc psql / ingest when the DB is toggled public."
  value       = aws_db_instance.this.address
}

output "master_user_secret_arn" {
  description = "ARN of the RDS-managed master password secret (JSON username/password). App Runner reads this at runtime."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}


output "vpc_connector_arn" {
  description = "App Runner VPC connector ARN."
  value       = aws_apprunner_vpc_connector.this.arn
}
