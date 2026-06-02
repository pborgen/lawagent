# Web frontend (Next.js 16) on its own App Runner service.
#
# Why a second service rather than static hosting: apps/web is NOT a
# static export. It runs server-side route handlers (/api/*), the OIDC
# auth flow (/auth/*), middleware (proxy.ts), and holds secrets
# (SESSION_SECRET, COGNITO_CLIENT_SECRET) server-side. It needs a Node
# server — so it mirrors the API: Docker image → ECR → App Runner.
#
# Differences from the API service (apprunner.tf):
#   - NO VPC connector. The web app only talks to the API and Cognito
#     over the public internet; it never touches the private RDS. Default
#     egress keeps it simple and avoids the per-AZ endpoint cost.
#   - Two genuinely-sensitive values (session signing key, Cognito client
#     secret) are injected from Secrets Manager via
#     runtime_environment_secrets, not as plaintext env vars.
#   - Health check hits "/" (the public landing page) — the web app has
#     no /health route, and "/" answers 200 without any auth env, which
#     is what lets the first apply go healthy before sign-in is wired.

locals {
  # Built from var.web_public_url, which is empty on the first apply (see
  # the variable's docs for the two-pass bootstrap).
  web_redirect_uri = var.web_public_url == "" ? "" : "${trimsuffix(var.web_public_url, "/")}/auth/callback"
  web_logout_uri   = var.web_public_url == "" ? "" : trimsuffix(var.web_public_url, "/")
}

# ---- ECR repo for the web image ---------------------------------------
resource "aws_ecr_repository" "web" {
  name                 = var.web_project_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "web" {
  repository = aws_ecr_repository.web.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 20 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}

# ---- Secrets injected at runtime --------------------------------------
# SESSION_SECRET: random, generated and owned by Terraform — it only has
# to be 32+ chars of entropy that stays stable across deploys (rotating it
# logs everyone out). recovery_window_in_days = 0 lets `terraform destroy`
# remove it immediately instead of soft-deleting for 7-30 days.
resource "random_password" "session_secret" {
  length  = 48
  special = false
}

resource "aws_secretsmanager_secret" "session_secret" {
  name                    = "${var.web_project_name}-session-secret"
  description             = "Next.js session-cookie signing key (SESSION_SECRET)."
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "session_secret" {
  secret_id     = aws_secretsmanager_secret.session_secret.id
  secret_string = random_password.session_secret.result
}

# COGNITO_CLIENT_SECRET: mirror of the user-pool client's secret. The web
# app uses it server-side for the OIDC code exchange; keeping it in
# Secrets Manager keeps it out of the App Runner env-var listing.
resource "aws_secretsmanager_secret" "cognito_client_secret" {
  name                    = "${var.web_project_name}-cognito-client-secret"
  description             = "Cognito web-client secret used by Next.js for the OIDC code exchange."
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "cognito_client_secret" {
  secret_id     = aws_secretsmanager_secret.cognito_client_secret.id
  secret_string = aws_cognito_user_pool_client.web.client_secret
}

# ---- Instance role (runtime identity of the web container) ------------
# Only needs to read its two secrets. No Bedrock/S3/DB access — the web
# tier never touches them; it proxies everything to the API.
data "aws_iam_policy_document" "web_instance_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["tasks.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "web_instance" {
  name               = "${var.web_project_name}-apprunner-instance"
  assume_role_policy = data.aws_iam_policy_document.web_instance_trust.json
}

data "aws_iam_policy_document" "web_instance" {
  statement {
    sid     = "ReadWebSecrets"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      aws_secretsmanager_secret.session_secret.arn,
      aws_secretsmanager_secret.cognito_client_secret.arn,
    ]
  }
}

resource "aws_iam_role_policy" "web_instance" {
  name   = "runtime"
  role   = aws_iam_role.web_instance.id
  policy = data.aws_iam_policy_document.web_instance.json
}

# ---- The web service itself -------------------------------------------
resource "aws_apprunner_service" "web" {
  service_name = var.web_project_name

  source_configuration {
    # Reuse the API's access role — it's a generic "App Runner may pull
    # from ECR" role, not API-specific.
    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_access.arn
    }

    auto_deployments_enabled = false

    image_repository {
      image_identifier      = "${aws_ecr_repository.web.repository_url}:${var.web_image_tag}"
      image_repository_type = "ECR"

      image_configuration {
        port = "3000"

        runtime_environment_variables = {
          # Where the browser-facing /api/* proxies forward to. Server-side
          # only — never exposed to the client.
          AGENT_API_URL = "https://${aws_apprunner_service.api.service_url}"

          # Cognito OIDC (non-secret half). The client secret comes in via
          # runtime_environment_secrets below.
          COGNITO_REGION              = var.aws_region
          COGNITO_USER_POOL_ID        = aws_cognito_user_pool.this.id
          COGNITO_CLIENT_ID           = aws_cognito_user_pool_client.web.id
          COGNITO_DOMAIN              = "https://${aws_cognito_user_pool_domain.this.domain}.auth.${var.aws_region}.amazoncognito.com"
          COGNITO_REDIRECT_URI        = local.web_redirect_uri
          COGNITO_LOGOUT_REDIRECT_URI = local.web_logout_uri
          # AUTH_DISABLED stays unset (defaults off) — real auth in prod.
        }

        runtime_environment_secrets = {
          SESSION_SECRET        = aws_secretsmanager_secret.session_secret.arn
          COGNITO_CLIENT_SECRET = aws_secretsmanager_secret.cognito_client_secret.arn
        }
      }
    }
  }

  # 0.5 vCPU / 1 GB — ample for a single-tenant Next SSR server, and a
  # tier cheaper than the API's 1 vCPU / 2 GB.
  instance_configuration {
    cpu               = "512"
    memory            = "1024"
    instance_role_arn = aws_iam_role.web_instance.arn
  }

  # No network_configuration block ⇒ default (public internet) egress.
  # The web tier reaches the API and Cognito over the internet; it has no
  # reason to enter the VPC.

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  # CI bumps the image tag every deploy; don't let `terraform apply` fight
  # the deploy workflow.
  lifecycle {
    ignore_changes = [
      source_configuration[0].image_repository[0].image_identifier,
    ]
  }
}
