# Cognito user pool with Google as a federated identity provider.
#
# Browser flow:
#   1. Next.js redirects to the Hosted UI
#      (https://<domain>.auth.<region>.amazoncognito.com/oauth2/authorize?...)
#   2. User clicks "Continue with Google" and signs in.
#   3. Cognito federates the identity, mints OIDC tokens, redirects back
#      to the Next.js callback URL with a code.
#   4. Next.js exchanges the code for tokens server-side and stores them
#      in an httpOnly session cookie.
#
# The FastAPI backend never talks to Cognito or Google — it just verifies
# the ID-token JWT against the user pool's JWKS on each request.
#
# Prerequisite (manual, in Google Cloud Console):
#   - Create an OAuth 2.0 Client ID of type "Web application".
#   - Authorized redirect URI:
#       https://<cognito_domain_prefix>.auth.<region>.amazoncognito.com/oauth2/idpresponse
#   - Pass the resulting client_id + client_secret in here via tfvars.

resource "aws_cognito_user_pool" "this" {
  name = "${var.project_name}-users"

  # We never let people register passwords directly — Google federation
  # is the only path in. Admins can still create users via the console
  # for emergency access.
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
}

# Hosted UI domain. AWS-managed subdomain under amazoncognito.com.
# Must be globally unique within the region.
resource "aws_cognito_user_pool_domain" "this" {
  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.this.id
}

# Google as a federated IdP. Cognito maps Google's claims onto the user
# pool's standard attributes; the mapping below copies email and the
# verification flag so the allowlist check can trust them.
resource "aws_cognito_identity_provider" "google" {
  user_pool_id  = aws_cognito_user_pool.this.id
  provider_name = "Google"
  provider_type = "Google"

  provider_details = {
    client_id        = var.google_client_id
    client_secret    = var.google_client_secret
    authorize_scopes = "openid email profile"
  }

  attribute_mapping = {
    email          = "email"
    email_verified = "email_verified"
    username       = "sub"
  }
}

# The Next.js app's OIDC client. Uses the authorization-code flow with a
# client secret, so the secret stays server-side in Next.js — never in
# the browser. PKCE adds defense-in-depth and is handled by Next.js.
resource "aws_cognito_user_pool_client" "web" {
  name         = "${var.project_name}-web"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret                      = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid", "email", "profile"]

  # Google federation only — no direct username/password auth on the pool.
  supported_identity_providers = [aws_cognito_identity_provider.google.provider_name]

  callback_urls = var.cognito_callback_urls
  logout_urls   = var.cognito_logout_urls

  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  # Token lifetimes — short ID/access tokens force regular refreshes,
  # long refresh token keeps the user signed in for ~30 days.
  id_token_validity      = 60 # minutes
  access_token_validity  = 60 # minutes
  refresh_token_validity = 30 # days

  token_validity_units {
    id_token      = "minutes"
    access_token  = "minutes"
    refresh_token = "days"
  }

  prevent_user_existence_errors = "ENABLED"
}

# The native mobile app's OIDC client (apps/mobile, Expo/React Native).
# A public client: `generate_secret = false`, because a secret can't be
# protected on a phone. Security comes from PKCE (the app generates a
# per-flow code verifier) plus the custom-scheme redirect. Tokens it mints
# carry this client's id as `aud`, so the API must list it in
# COGNITO_EXTRA_AUDIENCES to accept them (see apps/api/auth.py).
resource "aws_cognito_user_pool_client" "mobile" {
  name         = "${var.project_name}-mobile"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret                      = false
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid", "email", "profile"]

  supported_identity_providers = [aws_cognito_identity_provider.google.provider_name]

  # Custom URI scheme (e.g. lawagent://callback) — the app captures this
  # redirect via a deep link, not a web URL.
  callback_urls = var.cognito_mobile_callback_urls
  logout_urls   = var.cognito_mobile_logout_urls

  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  id_token_validity      = 60 # minutes
  access_token_validity  = 60 # minutes
  refresh_token_validity = 30 # days

  token_validity_units {
    id_token      = "minutes"
    access_token  = "minutes"
    refresh_token = "days"
  }

  prevent_user_existence_errors = "ENABLED"
}
