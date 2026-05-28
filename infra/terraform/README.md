# Terraform: lawagent AWS stack

Provisions everything the GitHub Actions deploy workflow needs:

- **ECR repo** (`lawagent-api`) with image scanning + lifecycle rule
- **GitHub OIDC provider** (skipped if you already have one)
- **GitHub deploy IAM role** — least-privilege, only your repo's `main` branch can assume it
- **App Runner service** running the API image on port 8000, hitting `/health`
- **App Runner access role** (ECR pull) + **instance role** (Bedrock invoke, S3 read/write)
- **Cognito user pool** with **Google** as a federated IdP, plus a Hosted-UI
  domain and an OIDC client for the Next.js web app

What's **not** here: the Postgres/pgvector database, Secrets Manager
entries for API keys, and the Next.js frontend. See "Things not in
this stack" below.

## Prerequisites

- Terraform ≥ 1.6
- AWS CLI configured with credentials that can create IAM, ECR, App Runner
- Bedrock model access enabled in your account & region (one-time, in
  the Bedrock console: "Model access")
- A pre-existing S3 bucket for case docs (this stack only grants access
  to it; it doesn't create it, to avoid Terraform accidentally owning
  bucket lifecycle)
- A reachable Postgres + pgvector URL (Aurora/RDS or otherwise)

## First-time apply

```bash
cd infra/terraform

cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars — fill in github_owner, github_repo, s3_bucket_name,
# lawagent_s3_uri, lawagent_pg_url

terraform init
terraform plan
terraform apply
```

App Runner needs *something* in ECR before it can start, so before the
first `apply` you have two options:

**Option A — push a placeholder first:**

```bash
# create the repo by itself, push an image, then apply the rest
terraform apply -target=aws_ecr_repository.api

aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin \
      "$(terraform output -raw ecr_repository_url | cut -d/ -f1)"

docker build -t lawagent-api ../..
docker tag lawagent-api:latest "$(terraform output -raw ecr_repository_url):latest"
docker push "$(terraform output -raw ecr_repository_url):latest"

terraform apply
```

**Option B — let CI push first:**

1. `terraform apply -target=aws_ecr_repository.api -target=aws_iam_role.github_deploy`
2. Set the GitHub variables/secrets (see below) for what exists so far
3. Push to `main` once → CI pushes `:latest` to ECR
4. `terraform apply` (now App Runner can find an image)

## Wiring GitHub Actions

After `terraform apply` finishes, run:

```bash
terraform output github_actions_setup
```

That prints the exact values to paste into **Settings → Secrets and
variables → Actions**:

- Variables: `AWS_REGION`, `AWS_ACCOUNT_ID`, `ECR_REPOSITORY`, `APP_RUNNER_SERVICE_ARN`
- Secret: `AWS_DEPLOY_ROLE_ARN`

## Day-2: how this stack interacts with CI

- The deploy workflow pushes a new image tag (`<git-sha>` and `latest`)
  and calls `aws apprunner start-deployment`. App Runner pulls `:latest`
  on each `start-deployment`.
- Terraform **ignores** drift on `source_configuration[0].image_repository[0].image_identifier`
  — so `terraform apply` won't fight the deploy workflow. To change the
  pinned image (e.g. to roll back), update `var.image_tag` and apply.
- Adding/changing env vars: edit `apprunner.tf` `runtime_environment_variables`
  and `terraform apply` — this *does* trigger an App Runner update.

## Cognito + Google federation (one-time)

Cognito needs a Google OAuth client. Google needs Cognito's redirect URL.
That's a circular dep, so the first apply runs in two passes:

1. **Apply once with placeholders.** Set `google_client_id` and
   `google_client_secret` to any non-empty string in `terraform.tfvars`,
   then `terraform apply`. Grab the redirect URL it prints:

   ```bash
   terraform output cognito_google_redirect_uri
   # https://lawagent-divorse.auth.us-east-1.amazoncognito.com/oauth2/idpresponse
   ```

2. **Create the Google OAuth client.** In Google Cloud Console →
   APIs & Services → Credentials → *Create credentials → OAuth client ID*:
   - Application type: **Web application**
   - Authorized redirect URIs: paste the URL from step 1
   - Save, copy the resulting client ID + secret.

3. **Re-apply with the real values.** Replace the placeholders in
   `terraform.tfvars` and `terraform apply` again.

4. **Wire the Next.js app.** Copy the outputs into `apps/web/.env.local`:

   ```bash
   terraform output cognito_user_pool_id      # COGNITO_USER_POOL_ID
   terraform output cognito_client_id         # COGNITO_CLIENT_ID
   terraform output cognito_client_secret     # COGNITO_CLIENT_SECRET (sensitive)
   terraform output cognito_hosted_ui_domain  # COGNITO_DOMAIN
   ```

   The FastAPI backend reads `COGNITO_REGION`, `COGNITO_USER_POOL_ID`,
   `COGNITO_CLIENT_ID`, and `COGNITO_ALLOWED_EMAILS`. In App Runner
   those four are wired automatically from this stack — no extra step.

## State

Local state by default. Migrate to S3 when you're ready:

1. Create a bucket (e.g. `lawagent-tfstate-<account-id>`)
2. Uncomment the `backend "s3"` block in [versions.tf](versions.tf)
3. `terraform init -migrate-state`

## Things not in this stack (yet)

- **Database**: App Runner doesn't host Postgres. Provision Aurora
  Serverless v2 with pgvector (or RDS Postgres) separately. To reach
  a private RDS instance, App Runner needs a **VPC connector** — add an
  `aws_apprunner_vpc_connector` and reference it from
  `network_configuration` in [apprunner.tf](apprunner.tf).
- **Secrets**: API keys (Anthropic, Voyage, etc.) should live in
  Secrets Manager, not in `runtime_environment_variables`. Use App
  Runner's `runtime_environment_secrets` to reference them by ARN
  once you have a secrets stack.
- **Frontend**: `apps/web` (Next.js) is not deployed here. Amplify
  Hosting or a second App Runner service are both viable; the latter
  needs its own Dockerfile.
- **Observability**: App Runner ships logs to CloudWatch automatically;
  custom dashboards / alarms aren't defined here.

## Destroying

```bash
terraform destroy
```

ECR repos with images in them won't delete unless you add
`force_delete = true` to the resource or empty them by hand first.
