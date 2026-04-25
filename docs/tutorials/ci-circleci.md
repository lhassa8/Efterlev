# CI integration: CircleCI

Stub for SPEC-38.6. Substantial content lands in a follow-up batch.

```yaml
# .circleci/config.yml
version: 2.1
jobs:
  efterlev-scan:
    docker:
      - image: ghcr.io/efterlev/efterlev:latest
    steps:
      - checkout
      - run: efterlev init --target . --baseline fedramp-20x-moderate
      - run: efterlev scan --target .
      - store_artifacts:
          path: .efterlev/reports/
workflows:
  pr:
    jobs:
      - efterlev-scan:
          filters:
            branches:
              ignore: main
```
