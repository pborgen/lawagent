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

output "aws_region" {
  description = "Value for the GitHub variable AWS_REGION."
  value       = var.aws_region
}

output "github_actions_setup" {
  description = "Paste-ready summary of what to add in GitHub repo settings."
  value       = <<-EOT

    GitHub Actions setup
    --------------------
    Settings → Secrets and variables → Actions

    Variables:
      AWS_REGION              = ${var.aws_region}
      AWS_ACCOUNT_ID          = ${data.aws_caller_identity.current.account_id}
      ECR_REPOSITORY          = ${aws_ecr_repository.api.name}
      APP_RUNNER_SERVICE_ARN  = ${aws_apprunner_service.api.arn}

    Secrets:
      AWS_DEPLOY_ROLE_ARN     = ${aws_iam_role.github_deploy.arn}

    Service URL: https://${aws_apprunner_service.api.service_url}
  EOT
}
