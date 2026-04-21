# aws.fips_ssl_policies_on_lb_listeners

Detects whether AWS load balancer TLS/HTTPS listeners use a FIPS-aligned
`ssl_policy` — specifically the `ELBSecurityPolicy-FS-*` forward-secrecy
families or the `ELBSecurityPolicy-TLS13-*` TLS 1.3 families.

Complement to `aws.tls_on_lb_listeners`: that detector proves the
listener accepts TLS; this one proves the chosen cipher policy is
FIPS-grade. Both must be "present" for the full "transport is
encrypted with FIPS-grade crypto" story.

## What this proves

- **KSI-SVC-VRI (Validating Resource Integrity), partial.** The chosen
  cipher policy is in a FIPS-aligned family (`ELBSecurityPolicy-FS-*`
  or `ELBSecurityPolicy-TLS13-*`).
- **KSI-SVC-SNT (Securing Network Traffic), reinforces.** Completes
  the algorithmic layer of the network-traffic-security story.
- **NIST SP 800-53 SC-13 (Cryptographic Protection), partial.**
  Infrastructure-layer evidence at the TLS termination point.

## What this does NOT prove

- **Certificate strength or key length.** The ssl_policy determines
  cipher suites, not certificate cryptography. ACM certificates with
  short RSA keys can still pair with a FIPS ssl_policy.
- **Runtime cipher-suite negotiation outcomes.** What the policy
  *permits* and what clients actually negotiate may differ.
- **Cryptographic-module validation.** AWS represents its LB service
  as operating FIPS 140-validated modules; this detector doesn't
  verify that representation independently.
- **Non-listener crypto.** S3 SSE algorithms, RDS at-rest encryption,
  SQS/SNS encryption, and custom KMS usage are separate signals
  handled by other detectors (or deferred).

## Allowlist rationale

We recognize two AWS ssl_policy families as FIPS-aligned:

- `ELBSecurityPolicy-FS-*` — forward-secrecy, AWS's recommended FedRAMP
  family.
- `ELBSecurityPolicy-TLS13-*` — TLS 1.3, modern ciphers only.

Legacy families like `ELBSecurityPolicy-2016-08` include cipher suites
that would fail a FedRAMP review and are flagged as `not_fips_approved`.
A user with a custom policy outside these prefixes will see a false
negative; the remediation is either rename to an AWS-published policy
or extend the allowlist here.

## Evidence shape

See `evidence.yaml`. Each TLS/HTTPS listener produces one Evidence
record with `fips_state ∈ {present, absent, unknown}`. Non-TLS
listeners are not covered (they're outside this detector's scope and
aws.tls_on_lb_listeners handles them).
