# AWS setup for CI/CD (click-ops fallback)

> **Primary path is Terraform** → see [../terraform/README.md](../terraform/README.md).
> This page is the manual CLI/console version, kept around as a
> reference for what the Terraform stack actually creates.

One-time setup so `.github/workflows/deploy.yml` can build the API
image, push it to ECR, and deploy to App Runner — all using GitHub
OIDC (no long-lived AWS keys in GitHub secrets).

Fill in the placeholders before running anything:

```
ACCOUNT=123456789012
REGION=us-east-1
REPO=lawagent-api
GH_OWNER=pborgen          # GitHub username/org
GH_REPO=lawagent          # GitHub repo name
```

---

## 1. Create the ECR repository

```bash
aws ecr create-repository \
  --repository-name "$REPO" \
  --image-scanning-configuration scanOnPush=true \
  --region "$REGION"
```

## 2. Wire up GitHub OIDC

Adds GitHub as a trusted OIDC identity provider in your account. Skip
if you already have it (only one per account).

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

## 3. Create the deploy role

The role GitHub Actions assumes via OIDC. Only trusts your repo's
`main` branch (and PRs against it — drop the `pull_request` line to
lock it down further).

**`trust-policy.json`:**

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::ACCOUNT:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:GH_OWNER/GH_REPO:ref:refs/heads/main"
      }
    }
  }]
}
```

**`deploy-policy.json`** — least-privilege: push to one ECR repo, deploy
to one App Runner service.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRAuth",
      "Effect": "Allow",
      "Action": "ecr:GetAuthorizationToken",
      "Resource": "*"
    },
    {
      "Sid": "ECRPush",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:CompleteLayerUpload",
        "ecr:InitiateLayerUpload",
        "ecr:PutImage",
        "ecr:UploadLayerPart"
      ],
      "Resource": "arn:aws:ecr:REGION:ACCOUNT:repository/REPO"
    },
    {
      "Sid": "AppRunnerDeploy",
      "Effect": "Allow",
      "Action": [
        "apprunner:StartDeployment",
        "apprunner:DescribeService"
      ],
      "Resource": "arn:aws:apprunner:REGION:ACCOUNT:service/lawagent-api/*"
    }
  ]
}
```

Create the role and attach the inline policy:

```bash
aws iam create-role \
  --role-name lawagent-github-deploy \
  --assume-role-policy-document file://trust-policy.json

aws iam put-role-policy \
  --role-name lawagent-github-deploy \
  --policy-name deploy \
  --policy-document file://deploy-policy.json
```

Note the role ARN — it goes into the GitHub secret `AWS_DEPLOY_ROLE_ARN`.

## 4. Create the App Runner service

Easiest path is the AWS console (`App Runner → Create service`):

- **Source**: Container registry → Amazon ECR → browse to `lawagent-api:latest`
- **Deployment trigger**: **Manual** (the workflow calls `start-deployment`
  per commit — keeps rollouts tied to a specific SHA, not whatever's
  tagged `latest`)
- **Port**: `8000`
- **Health check**: HTTP path `/health`
- **Instance role**: a role with `AmazonBedrockFullAccess` (or scoped
  Bedrock access) + read access to your S3 bucket. App Runner uses this
  for runtime calls, not for deploy.
- **Environment variables / secrets**: set `LAWAGENT_PROFILE=bedrock`,
  `LAWAGENT_S3_URI=...`, `LAWAGENT_PG_URL=...`, etc. Put API keys in
  Secrets Manager and reference them by ARN.

After it's running, note the service ARN — that goes into the GitHub
variable `APP_RUNNER_SERVICE_ARN`.

## 5. Add GitHub repo settings

In `Settings → Secrets and variables → Actions`:

**Variables:**

| Name                     | Example                                                      |
| ------------------------ | ------------------------------------------------------------ |
| `AWS_REGION`             | `us-east-1`                                                  |
| `AWS_ACCOUNT_ID`         | `123456789012`                                               |
| `ECR_REPOSITORY`         | `lawagent-api`                                               |
| `APP_RUNNER_SERVICE_ARN` | `arn:aws:apprunner:us-east-1:123…:service/lawagent-api/abc…` |

**Secrets:**

| Name                  | Example                                                |
| --------------------- | ------------------------------------------------------ |
| `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::123456789012:role/lawagent-github-deploy` |

## 6. Test it

```bash
# from main, after the workflow has been merged:
git commit --allow-empty -m "trigger first deploy"
git push origin main
```

Watch the run under `Actions → Deploy`. First deploy takes a few
minutes (App Runner provisions a service); subsequent rollouts are
much faster.

---

## Things that aren't here yet

- **Database**: App Runner has no managed Postgres. Stand up Aurora
  Serverless v2 (pgvector-enabled) or RDS Postgres in the same region
  and put its URL in `LAWAGENT_PG_URL`. App Runner needs a VPC
  connector to reach a private RDS instance.
- **Frontend**: `apps/web` (Next.js) isn't deployed by this pipeline.
  Easiest target is Amplify Hosting or Vercel; or build a second
  Dockerfile + App Runner service.
- **IaC**: this is all click-ops / one-shot CLI. Once it's stable,
  port to CDK (Python — fits the monorepo) or Terraform.
- **Staging**: single environment. Add a `develop` branch + a second
  App Runner service when ready.
