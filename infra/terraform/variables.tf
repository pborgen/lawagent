variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short name used as a prefix for resources (ECR repo, App Runner service, IAM roles)."
  type        = string
  default     = "lawagent-api"
}

variable "github_owner" {
  description = "GitHub username or org that owns the repo (e.g. \"pborgen\")."
  type        = string
}

variable "github_repo" {
  description = "GitHub repo name (e.g. \"lawagent\")."
  type        = string
}

variable "github_oidc_provider_arn" {
  description = <<-EOT
    ARN of the existing GitHub Actions OIDC provider in this account.
    Leave empty to have Terraform create it (only one is allowed per account —
    if you already have one for another repo, paste its ARN here instead).
  EOT
  type        = string
  default     = ""
}

variable "s3_bucket_name" {
  description = "S3 bucket holding case docs. Granted to the App Runner instance role."
  type        = string
}

variable "lawagent_profile" {
  description = "Value for LAWAGENT_PROFILE env var (e.g. \"bedrock\")."
  type        = string
  default     = "bedrock"
}

variable "lawagent_s3_uri" {
  description = "Value for LAWAGENT_S3_URI env var (e.g. \"s3://my-bucket/case/\")."
  type        = string
}

variable "lawagent_pg_url" {
  description = "Postgres + pgvector connection URL. Stored as a runtime env var on the App Runner service."
  type        = string
  sensitive   = true
}

variable "image_tag" {
  description = "ECR image tag App Runner should run on initial create. Use \"latest\" for first apply, then let the GitHub deploy workflow roll out specific SHAs."
  type        = string
  default     = "latest"
}

# --- Cognito ---------------------------------------------------------

variable "cognito_domain_prefix" {
  description = <<-EOT
    Globally-unique subdomain for the Cognito Hosted UI under
    amazoncognito.com. Lowercase letters, digits, and hyphens only.
    Example: "lawagent-divorse" → https://lawagent-divorse.auth.us-east-1.amazoncognito.com
  EOT
  type        = string
}

variable "google_client_id" {
  description = "OAuth 2.0 client ID from Google Cloud Console (Web application type)."
  type        = string
  sensitive   = true
}

variable "google_client_secret" {
  description = "OAuth 2.0 client secret matching google_client_id."
  type        = string
  sensitive   = true
}

variable "cognito_callback_urls" {
  description = <<-EOT
    Allowed OAuth redirect URIs for the Next.js web client. Include the
    dev origin and any deployed origin(s). The path is always
    /auth/callback.
  EOT
  type        = list(string)
  default     = ["http://localhost:3000/auth/callback"]
}

variable "cognito_logout_urls" {
  description = "Allowed post-sign-out redirect URIs for the Next.js web client."
  type        = list(string)
  default     = ["http://localhost:3000"]
}

variable "cognito_allowed_emails" {
  description = <<-EOT
    Comma-separated email allowlist enforced by the FastAPI backend.
    Even if someone authenticates with Cognito/Google, requests are
    rejected unless their verified email matches one in this list.
  EOT
  type        = string
}
