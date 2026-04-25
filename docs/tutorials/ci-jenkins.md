# CI integration: Jenkins

Stub for SPEC-38.6. Substantial content lands in a follow-up batch.

```groovy
pipeline {
  agent {
    docker { image 'ghcr.io/efterlev/efterlev:latest' }
  }
  stages {
    stage('Compliance scan') {
      steps {
        sh 'efterlev init --target . --baseline fedramp-20x-moderate'
        sh 'efterlev scan --target .'
        archiveArtifacts artifacts: '.efterlev/reports/**', allowEmptyArchive: true
      }
    }
  }
}
```
