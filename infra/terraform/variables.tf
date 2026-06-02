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

# --- Bedrock guardrail thresholds ------------------------------------
# Contextual-grounding confidence floors, 0.00–0.99. An answer scoring
# below the threshold is BLOCKED. Higher = stricter (fewer ungrounded
# answers slip through, but more borderline-but-valid answers get refused).

variable "guardrail_grounding_threshold" {
  description = "Min grounding confidence (answer supported by retrieved passages). Below this → blocked."
  type        = number
  default     = 0.75
}

variable "guardrail_relevance_threshold" {
  description = "Min relevance confidence (answer addresses the question). Below this → blocked."
  type        = number
  default     = 0.5
}

variable "lawagent_pg_url" {
  description = "DEPRECATED — the connection URL is now constructed from the RDS instance in rds.tf (local.pg_url). Set db_password instead. Kept only so existing tfvars don't error; safe to delete."
  type        = string
  sensitive   = true
  default     = ""
}

variable "image_tag" {
  description = "ECR image tag App Runner should run on initial create. Use \"latest\" for first apply, then let the GitHub deploy workflow roll out specific SHAs."
  type        = string
  default     = "latest"
}

# --- Web frontend (Next.js on a second App Runner service) -----------

variable "web_project_name" {
  description = "Short name / prefix for the web frontend's resources (ECR repo, App Runner service, IAM role, secrets)."
  type        = string
  default     = "lawagent-web"
}

variable "web_image_tag" {
  description = "ECR image tag the web App Runner service runs on initial create. Same story as image_tag — \"latest\" for the first apply, then CI rolls out SHAs."
  type        = string
  default     = "latest"
}

variable "web_public_url" {
  description = <<-EOT
    Public origin of the deployed web app, e.g.
    "https://abc123.us-east-1.awsapprunner.com" (no trailing slash).
    Used to build COGNITO_REDIRECT_URI (/auth/callback) and the logout
    URL injected into the web service.

    CHICKEN-AND-EGG: App Runner mints this URL only after the service is
    created, and a resource can't reference its own computed URL. So the
    bootstrap is two passes:
      1. Leave this "" and apply — the service comes up healthy (the
         landing page needs no auth env), but sign-in is not wired yet.
      2. Read `terraform output web_service_url`, set it here AND add it
         to cognito_callback_urls / cognito_logout_urls, then apply again.
  EOT
  type        = string
  default     = ""
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

variable "cognito_mobile_callback_urls" {
  description = <<-EOT
    Allowed OAuth redirect URIs for the native mobile client (apps/mobile).
    Custom URI scheme captured by the app as a deep link, not a web URL.
  EOT
  type        = list(string)
  default     = ["lawagent://callback"]
}

variable "cognito_mobile_logout_urls" {
  description = "Allowed post-sign-out redirect URIs for the native mobile client."
  type        = list(string)
  default     = ["lawagent://callback"]
}

variable "cognito_allowed_emails" {
  description = <<-EOT
    Comma-separated email allowlist enforced by the FastAPI backend.
    Even if someone authenticates with Cognito/Google, requests are
    rejected unless their verified email matches one in this list.
  EOT
  type        = string
}
