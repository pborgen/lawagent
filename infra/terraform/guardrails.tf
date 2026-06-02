# Amazon Bedrock Guardrail for the agent's answers.
#
# This is the platform-layer backstop behind the agent's system prompt: the
# product's whole value is grounded, checkable citations, and a hallucinated
# cite is the failure mode that kills it. The four policies below map 1:1 to
# how packages/llm/guardrails.py reacts:
#
#   - contextual grounding  → block ungrounded / irrelevant answers
#   - denied topics         → block judge-outcome prediction & off-scope asks
#   - content + prompt-attack filters → block toxicity / jailbreaks
#   - sensitive information  → mask financial PII in answers
#
# The App Runner instance role gets bedrock:ApplyGuardrail (apprunner.tf),
# and the guardrail id + version are injected as env vars so the running
# container picks them up. ApplyGuardrail rides the existing bedrock-runtime
# VPC endpoint (network.tf) — no new endpoint needed.

resource "aws_bedrock_guardrail" "this" {
  name        = "${var.project_name}-guardrail"
  description = "Grounding + scope + PII guardrail for the CT divorce agent."

  # Required by the API. Our app generates its own user-facing refusals
  # (llm.guardrails), so these are fallbacks that should rarely be seen.
  blocked_input_messaging   = "This request can't be processed."
  blocked_outputs_messaging = "I can't provide a grounded answer to that."

  # ── Contextual grounding — the anti-hallucination check ────────────────
  # GROUNDING: is the answer supported by the retrieved passages?
  # RELEVANCE: does the answer actually address the question?
  # Below threshold → the filter BLOCKS (our code maps that to a refusal).
  contextual_grounding_policy_config {
    filters_config {
      type      = "GROUNDING"
      threshold = var.guardrail_grounding_threshold
    }
    filters_config {
      type      = "RELEVANCE"
      threshold = var.guardrail_relevance_threshold
    }
  }

  # ── Denied topics — reinforce the system prompt's hard rules ───────────
  topic_policy_config {
    topics_config {
      name       = "JudicialOutcomePrediction"
      type       = "DENY"
      definition = "Predicting, estimating, or handicapping how a specific judge, court, or proceeding will rule or decide an issue."
      examples = [
        "How will the judge rule on my alimony request?",
        "What are my chances of winning custody?",
        "Will Judge Smith grant my motion?",
      ]
    }
    topics_config {
      name       = "OutOfScopeLegalDomain"
      type       = "DENY"
      definition = "Legal questions outside Connecticut family and divorce law, such as criminal defense, immigration, or the law of other states."
      examples = [
        "How do I fight a DUI charge?",
        "What are the divorce laws in California?",
      ]
    }
  }

  # ── Content + prompt-attack filters ────────────────────────────────────
  # PROMPT_ATTACK is input-only (output_strength must be NONE).
  content_policy_config {
    filters_config {
      type            = "HATE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "INSULTS"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "SEXUAL"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "VIOLENCE"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "MISCONDUCT"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
  }

  # ── Sensitive information — mask financial PII in answers ──────────────
  # Deliberately scoped to financial / credential PII. We do NOT anonymize
  # names, emails, phones, or addresses: a divorce answer legitimately
  # references parties, the court, and case contacts, and masking those
  # would gut the response. ANONYMIZE swaps a placeholder in rather than
  # blocking, so the answer survives minus the sensitive token.
  sensitive_information_policy_config {
    pii_entities_config {
      type   = "US_SOCIAL_SECURITY_NUMBER"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "US_INDIVIDUAL_TAX_IDENTIFICATION_NUMBER"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "US_BANK_ACCOUNT_NUMBER"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "US_BANK_ROUTING_NUMBER"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "CREDIT_DEBIT_CARD_NUMBER"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "CREDIT_DEBIT_CARD_CVV"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "PIN"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "PASSWORD"
      action = "ANONYMIZE"
    }
  }
}

# A numbered, immutable version to point the app at. The DRAFT moves as you
# edit the guardrail; a published version is a frozen snapshot. CI/prod use
# this version number (wired into App Runner env in apprunner.tf).
resource "aws_bedrock_guardrail_version" "this" {
  guardrail_arn = aws_bedrock_guardrail.this.guardrail_arn
  description   = "Published version consumed by the App Runner service."
}
