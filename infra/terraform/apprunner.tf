# App Runner needs two service roles:
#  - access role:    used by App Runner itself to pull from ECR
#  - instance role:  the running container's AWS identity (Bedrock, S3)

# ---- access role (ECR pull) -------------------------------------------
data "aws_iam_policy_document" "apprunner_access_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["build.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "apprunner_access" {
  name               = "${var.project_name}-apprunner-access"
  assume_role_policy = data.aws_iam_policy_document.apprunner_access_trust.json
}

resource "aws_iam_role_policy_attachment" "apprunner_access_ecr" {
  role       = aws_iam_role.apprunner_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# ---- instance role (runtime AWS access from the container) ------------
data "aws_iam_policy_document" "apprunner_instance_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["tasks.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "apprunner_instance" {
  name               = "${var.project_name}-apprunner-instance"
  assume_role_policy = data.aws_iam_policy_document.apprunner_instance_trust.json
}

data "aws_iam_policy_document" "apprunner_instance" {
  # Bedrock invoke for the `bedrock` profile. Scoped to the region this
  # service runs in; AnyResource is the model ARN, which Bedrock treats
  # as opaque ARNs per model id.
  statement {
    sid = "BedrockInvoke"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]
    resources = ["*"]
  }

  # Case docs in S3 — list the bucket, read/write objects.
  statement {
    sid       = "S3Bucket"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = ["arn:aws:s3:::${var.s3_bucket_name}"]
  }

  statement {
    sid = "S3Objects"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["arn:aws:s3:::${var.s3_bucket_name}/*"]
  }

  # Fetch the RDS-managed master password at runtime (rotation-safe).
  statement {
    sid       = "ReadDbSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_db_instance.this.master_user_secret[0].secret_arn]
  }

  # Decrypt that secret. The default aws/secretsmanager key allows this
  # implicitly; scoping to the secret's key also covers a customer-managed key.
  statement {
    sid       = "DecryptDbSecret"
    actions   = ["kms:Decrypt"]
    resources = [aws_db_instance.this.master_user_secret[0].kms_key_id]
  }
}

resource "aws_iam_role_policy" "apprunner_instance" {
  name   = "runtime"
  role   = aws_iam_role.apprunner_instance.id
  policy = data.aws_iam_policy_document.apprunner_instance.json
}

# ---- the service itself -----------------------------------------------
resource "aws_apprunner_service" "api" {
  service_name = var.project_name

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_access.arn
    }

    # Manual deploys — the GitHub workflow calls start-deployment so
    # each rollout is tied to a specific commit, not whatever's :latest.
    auto_deployments_enabled = false

    image_repository {
      image_identifier      = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
      image_repository_type = "ECR"

      image_configuration {
        port = "8000"

        runtime_environment_variables = {
          LAWAGENT_PROFILE = var.lawagent_profile
          LAWAGENT_S3_URI  = var.lawagent_s3_uri
          AWS_REGION       = var.aws_region
          # DB connection parts. The password is NOT here — the container
          # fetches it from the RDS-managed secret at runtime (rotation-safe).
          LAWAGENT_PG_HOST       = aws_db_instance.this.address
          LAWAGENT_PG_PORT       = "5432"
          LAWAGENT_PG_DB         = var.db_name
          LAWAGENT_PG_SECRET_ARN = aws_db_instance.this.master_user_secret[0].secret_arn
          # Auth: verify the Cognito JWT and enforce the email allowlist
          # on every request. AUTH_DISABLED stays unset in prod.
          COGNITO_REGION         = var.aws_region
          COGNITO_USER_POOL_ID   = aws_cognito_user_pool.this.id
          COGNITO_CLIENT_ID      = aws_cognito_user_pool_client.web.id
          COGNITO_ALLOWED_EMAILS = var.cognito_allowed_emails
        }
      }
    }
  }

  instance_configuration {
    cpu               = "1024" # 1 vCPU
    memory            = "2048" # 2 GB
    instance_role_arn = aws_iam_role.apprunner_instance.arn
  }

  # Route the app's outbound traffic through the VPC so it can reach the
  # private RDS. Bedrock / Cognito / S3 are reached via the VPC endpoints
  # in network.tf (a VPC connector otherwise cuts off public egress).
  network_configuration {
    egress_configuration {
      egress_type       = "VPC"
      vpc_connector_arn = aws_apprunner_vpc_connector.this.arn
    }
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  # The image_identifier changes every deploy (the GitHub workflow
  # bumps it). Don't let `terraform apply` fight the deploy workflow.
  lifecycle {
    ignore_changes = [
      source_configuration[0].image_repository[0].image_identifier,
    ]
  }
}
