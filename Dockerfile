# syntax=docker/dockerfile:1.7
#
# Two-stage build:
#   - builder: produces a wheel from source (catalogs ride along via
#     [tool.hatch.build.targets.wheel.force-include] in pyproject.toml)
#   - runtime: minimal layer with only the installed wheel + deps
#
# See SPEC-06 for the full design rationale.

FROM python:3.12-slim-bookworm AS builder

RUN pip install --no-cache-dir uv
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY catalogs/ ./catalogs/
RUN uv build --wheel

FROM python:3.12-slim-bookworm

# OCI labels — the org.opencontainers.image.* set is the standard for
# registries and GitHub "Packages" UI.
LABEL org.opencontainers.image.title="Efterlev"
LABEL org.opencontainers.image.description="Repo-native, agent-first compliance scanner for FedRAMP 20x"
LABEL org.opencontainers.image.source="https://github.com/efterlev/efterlev"
LABEL org.opencontainers.image.documentation="https://efterlev.com"
LABEL org.opencontainers.image.vendor="Efterlev project"
LABEL org.opencontainers.image.licenses="Apache-2.0"

COPY --from=builder /src/dist/*.whl /tmp/
# Install with the [bedrock] extra so the AWS Bedrock backend (SPEC-10) is
# usable out of the box for GovCloud-EC2 deployments. boto3 + botocore add
# ~17 MB but avoid an extra install step inside the customer's network
# boundary, which is the whole point of running in the container.
RUN WHEEL=$(ls /tmp/*.whl) && pip install --no-cache-dir "${WHEEL}[bedrock]" && rm /tmp/*.whl

# Mount point for the user's repo:
#   docker run --rm -v $(pwd):/repo ghcr.io/efterlev/efterlev scan /repo
WORKDIR /repo

ENTRYPOINT ["efterlev"]
CMD ["--help"]
