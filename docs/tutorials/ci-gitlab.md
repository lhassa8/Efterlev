# CI integration: GitLab CI

Stub for SPEC-38.6. Substantial content lands in a follow-up batch.

The pattern: install Efterlev via `pipx` or pull the container, run `efterlev init && efterlev scan`, optionally `efterlev agent gap`, post results as MR notes via the GitLab API.

```yaml
# .gitlab-ci.yml
efterlev-scan:
  image: ghcr.io/efterlev/efterlev:latest
  stage: test
  script:
    - efterlev init --target . --baseline fedramp-20x-moderate
    - efterlev scan --target .
  artifacts:
    paths:
      - .efterlev/reports/
    when: always
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes:
        - "**/*.tf"
        - "**/*.tfvars"
        - ".efterlev/manifests/**"
```

A scan-action-equivalent for GitLab — including the sticky-MR-note post — is a community contribution opportunity. Until that exists, this skeleton is enough to get scan output as a downloadable artifact.
