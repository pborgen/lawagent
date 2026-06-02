output "ecr_repository_url" {
  description = "Push images here (used by the GitHub deploy workflow)."
  value       = aws_ecr_repository.api.repository_url
}

output "ecr_repository_name" {
  description = "Value for the GitHub variable ECR_REPOSITORY."
  value       = aws_ecr_repository.api.name
}

output "github_deploy_role_arn" {
  description = "Value for the GitHub secret AWS_DEPLOY_ROLE_ARN."
  value       = aws_iam_role.github_deploy.arn
}

output "app_runner_service_arn" {
  description = "Value for the GitHub variable APP_RUNNER_SERVICE_ARN."
  value       = aws_apprunner_service.api.arn
}

output "app_runner_service_url" {
  description = "Public HTTPS URL of the running service."
  value       = "https://${aws_apprunner_service.api.service_url}"
}

output "aws_account_id" {
  description = "Value for the GitHub variable AWS_ACCOUNT_ID."
  value       = data.aws_caller_identity.current.account_id
}

# --- Web frontend ----------------------------------------------------

output "web_ecr_repository_name" {
  description = "Value for the GitHub variable WEB_ECR_REPOSITORY."
  value       = aws_ecr_repository.web.name
}

output "web_app_runner_service_arn" {
  description = "Value for the GitHub variable WEB_APP_RUNNER_SERVICE_ARN."
  value       = aws_apprunner_service.web.arn
}

output "web_service_url" {
  description = <<-EOT
    Public HTTPS URL of the web app. After the first apply, set this as
    var.web_public_url AND add "<url>/auth/callback" to
    cognito_callback_urls and "<url>" to cognito_logout_urls, then apply
    again to finish wiring sign-in.
  EOT
  value       = "https://${aws_apprunner_service.web.service_url}"
}

output "aws_region" {
  description = "Value for the GitHub variable AWS_REGION."
  value       = var.aws_region
}

# --- Bedrock guardrail -----------------------------------------------

output "bedrock_guardrail_id" {
  description = "Value for the FastAPI env var LAWAGENT_BEDROCK_GUARDRAIL_ID."
  value       = aws_bedrock_guardrail.this.guardrail_id
}

output "bedrock_guardrail_version" {
  description = "Value for the FastAPI env var LAWAGENT_BEDROCK_GUARDRAIL_VERSION."
  value       = aws_bedrock_guardrail_version.this.version
}

# --- Cognito ---------------------------------------------------------

output "cognito_user_pool_id" {
  description = "Value for the FastAPI env var COGNITO_USER_POOL_ID."
  value       = aws_cognito_user_pool.this.id
}

output "cognito_client_id" {
  description = "OIDC client ID. Used by both Next.js (COGNITO_CLIENT_ID) and FastAPI (audience claim)."
  value       = aws_cognito_user_pool_client.web.id
}

output "cognito_mobile_client_id" {
  description = <<-EOT
    Native mobile (apps/mobile) OIDC client ID. Set this as
    EXPO_PUBLIC_COGNITO_CLIENT_ID in the app, and add it to the API's
    COGNITO_EXTRA_AUDIENCES so its tokens are accepted.
  EOT
  value       = aws_cognito_user_pool_client.mobile.id
}

output "cognito_client_secret" {
  description = "OIDC client secret. Used by Next.js only (COGNITO_CLIENT_SECRET). Treat as a secret."
  value       = aws_cognito_user_pool_client.web.client_secret
  sensitive   = true
}

output "cognito_hosted_ui_domain" {
  description = "Base URL of the Cognito Hosted UI (COGNITO_DOMAIN for Next.js)."
  value       = "https://${aws_cognito_user_pool_domain.this.domain}.auth.${var.aws_region}.amazoncognito.com"
}

output "cognito_issuer" {
  description = "OIDC issuer URL. FastAPI verifies this in the JWT 'iss' claim."
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.this.id}"
}

output "cognito_google_redirect_uri" {
  description = "Paste this into the Google Cloud Console as an authorized redirect URI."
  value       = "https://${aws_cognito_user_pool_domain.this.domain}.auth.${var.aws_region}.amazoncognito.com/oauth2/idpresponse"
}

output "github_actions_setup" {
  description = "Paste-ready summary of what to add in GitHub repo settings."
  value       = <<-EOT

    GitHub Actions setup
    --------------------
    Settings → Secrets and variables → Actions

    Variables:
      AWS_REGION                  = ${var.aws_region}
      AWS_ACCOUNT_ID              = ${data.aws_caller_identity.current.account_id}
      ECR_REPOSITORY              = ${aws_ecr_repository.api.name}
      APP_RUNNER_SERVICE_ARN      = ${aws_apprunner_service.api.arn}
      WEB_ECR_REPOSITORY          = ${aws_ecr_repository.web.name}
      WEB_APP_RUNNER_SERVICE_ARN  = ${aws_apprunner_service.web.arn}

    Secrets:
      AWS_DEPLOY_ROLE_ARN         = ${aws_iam_role.github_deploy.arn}

    API URL: https://${aws_apprunner_service.api.service_url}
    Web URL: https://${aws_apprunner_service.web.service_url}
  EOT
}
