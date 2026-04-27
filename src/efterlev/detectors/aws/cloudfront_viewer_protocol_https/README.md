# `aws.cloudfront_viewer_protocol_https`

Inspects every `aws_cloudfront_distribution` and reports whether viewer connections are HTTPS-only and whether the minimum TLS version meets a FedRAMP-acceptable bar.

## What this detector evidences

- **KSI-SVC-VCM** (Validating Communications).
- **800-53 controls:** SC-23 (Session Authenticity), SI-7(1) (Integrity Checks).

## What it proves

For each CloudFront distribution, the detector inspects:

1. Every cache behavior (`default_cache_behavior` + each `ordered_cache_behavior`)'s `viewer_protocol_policy`. CloudFront accepts `allow-all`, `https-only`, or `redirect-to-https`. The first allows plaintext HTTP through to the origin; the others do not.
2. The `viewer_certificate.minimum_protocol_version`. CloudFront's options range from SSLv3 (deprecated) up through `TLSv1.2_2021` and `TLSv1.3`. Below TLSv1.2 is below the FedRAMP-acceptable cipher floor.

One Evidence is emitted per distribution with `viewer_state` ∈ `{https_only, allows_http, mixed, unknown}` and `tls_meets_fedramp_bar` (bool).

## Why this matters

CloudFront sits at the edge — it is the surface every viewer interacts with. A distribution that allows `allow-all` accepts plaintext HTTP, which can be MITM'd before reaching the redirect (if any). A distribution with `minimum_protocol_version` unset defaults to `TLSv1` — vulnerable to BEAST/POODLE-class downgrade attacks. Both knobs together evidence SC-23 (session authenticity) and SI-7(1) (per-message integrity via TLS HMAC).

## What it does NOT prove

- That the certificate is valid for the served hostname or in date.
- That the `origin_protocol_policy` (CloudFront → origin) is HTTPS — that's a different surface scoped to a future detector.
- That HSTS or secure-cookie headers are sent — those live in CloudFront response-headers policies and the origin application.
- That the WAF in front of the distribution is configured (a separate KSI-CNA-DFP concern).

## Detection signal

One Evidence record per CloudFront distribution. The `gap` field populates whenever `viewer_state ∈ {allows_http, mixed}` or `tls_meets_fedramp_bar` is false.

## Known limitations

- Distributions built via `dynamic "default_cache_behavior"` blocks render as `${...}` placeholders from HCL alone; the detector classifies these as `viewer_state="unknown"`. Plan-JSON mode resolves the dynamic blocks and produces concrete evidence.
- The `minimum_protocol_version` allowlist is conservative — `TLSv1.2_2018` is the earliest version we accept. Customers running stricter policies (`TLSv1.3` only) are correctly classified as meeting the bar.
