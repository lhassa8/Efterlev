# Deploy air-gapped

Stub for SPEC-38.8. Substantial content lands in a follow-up batch.

The pattern, in shorthand:

1. Mirror `ghcr.io/efterlev/efterlev:vX.Y.Z` into your private registry.
2. Configure Bedrock backend (SPEC-10) with a VPC endpoint so all LLM traffic stays inside your boundary.
3. Block egress to `anthropic.com` at the security-group level; verify the Bedrock-only path works.
4. Block egress to `pypi.org` and `ghcr.io` post-deployment; the running container has everything it needs.

True air-gap (no internet at all, including for AWS API calls to a public Bedrock endpoint) requires a local LLM backend; that's v1.5+ work. For the realistic GovCloud-style "boundary-isolated" deployment, the [GovCloud deploy tutorial](deploy-govcloud-ec2.md) is the canonical reference.
