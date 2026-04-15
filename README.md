# Jenkins Shared Library — Microservice Pipeline Templates

A centralized Jenkins Shared Library that standardizes CI/CD workflows across application teams. Complex pipeline logic is abstracted into a single declarative wrapper, paired with Python-based pre-flight validation to ensure environment integrity.

---

## Repository Structure

```text
jenkins-shared-lib/
├── vars/
│   ├── standardMicroservicePipeline.groovy   # Main pipeline wrapper
│   ├── buildApp.groovy                       # Build stage
│   ├── testApp.groovy                        # Test stage
│   ├── buildAndPushContainer.groovy          # Container build & push
│   └── deployApp.groovy                      # Deployment stage
├── resources/
│   └── scripts/
│       └── validate_env.py                   # Pre-flight env validation
├── tests/
│   └── test_validate_env.py                  # Unit tests (11 tests)
├── examples/
│   ├── Jenkinsfile                           # Optimized consumer (<20 lines)
│   └── Jenkinsfile.traditional               # Traditional comparison (258 lines)
├── src/                                      # Reserved for future use
└── README.md
```

---

## Quick Start

### 1. Register the Library in Jenkins

Go to **Manage Jenkins → System → Global Pipeline Libraries** and add:

| Field              | Value                                          |
|--------------------|------------------------------------------------|
| **Name**           | `jenkins-shared-lib`                           |
| **Default Version**| `main`                                         |
| **Retrieval**      | Modern SCM → Git                               |
| **Project URL**    | `https://github.com/<org>/jenkins-shared-lib`  |

### 2. Create a Consumer Jenkinsfile

In the root of your application repository, create a `Jenkinsfile`:

```groovy
@Library('jenkins-shared-lib') _

standardMicroservicePipeline(
    appName:        'order-service',
    appPort:         8080,
    deployEnv:      'staging',
    dockerRegistry: 'registry.example.com',
)
```

**That's it.** 7 lines of effective code instead of 200+. See `examples/Jenkinsfile.traditional` for the full comparison.

---

## Configuration Reference

### Required Parameters

| Parameter        | Type     | Description                                    |
|------------------|----------|------------------------------------------------|
| `appName`        | `String` | Name of the application / service              |
| `appPort`        | `int`    | Port the application listens on                |
| `deployEnv`      | `String` | Target environment (`staging`, `production`)   |
| `dockerRegistry` | `String` | Container registry URL                         |

### Optional Parameters

| Parameter        | Type     | Default                         | Description                          |
|------------------|----------|---------------------------------|--------------------------------------|
| `buildCmd`       | `String` | `./gradlew clean build`         | Shell command for the build step     |
| `testCmd`        | `String` | `./gradlew test`                | Shell command for the test step      |
| `dockerfilePath` | `String` | `Dockerfile`                    | Path to the Dockerfile               |
| `imageName`      | `String` | `<registry>/<appName>`          | Full image name override             |
| `imageTag`       | `String` | `${BUILD_NUMBER}` or `latest`   | Image tag override                   |
| `deployTarget`   | `String` | `<appName>-<deployEnv>`         | Container/service name on the host   |
| `deployCmd`      | `String` | *(SSH + docker run)*            | Fully custom deploy command          |

---

## Pre-flight Validation

The Python validation script (`resources/scripts/validate_env.py`) runs at the very start of every pipeline execution. It checks that all required environment variables and secrets are present **before** any compute-heavy stages run.

### Variables Checked

| Variable          | Stage             | Description                              |
|-------------------|-------------------|------------------------------------------|
| `APP_NAME`        | all               | Application name                         |
| `DEPLOY_ENV`      | deploy            | Target deployment environment            |
| `DOCKER_REGISTRY` | build-container   | Container registry URL                   |
| `DOCKER_USER`     | build-container   | Docker registry username                 |
| `DOCKER_PASS`     | build-container   | Docker registry password / token         |
| `DEPLOY_HOST`     | deploy            | Target host IP or hostname               |

If any variable is missing, the script exits with code `1` and the pipeline **aborts immediately**, saving time and compute resources.

### Local Testing

```bash
# All vars set → should pass
APP_NAME=my-svc DEPLOY_ENV=staging DOCKER_REGISTRY=r.io \
DOCKER_USER=admin DOCKER_PASS=secret DEPLOY_HOST=10.0.0.1 \
python3 resources/scripts/validate_env.py

# No vars set → should fail with exit code 1
python3 resources/scripts/validate_env.py
```

---

## Pipeline Stages

```text
┌──────────────────────┐
│ Pre-flight Validation│  ← Python env check
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│       Build          │  ← buildApp.groovy
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│       Test           │  ← testApp.groovy
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Build & Push Image   │  ← buildAndPushContainer.groovy
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│       Deploy         │  ← deployApp.groovy
└──────────┘───────────┘
```

---

## Jenkins Credentials Required

Configure these in **Manage Jenkins → Credentials**:

| Credential ID                  | Type               | Description                        |
|--------------------------------|--------------------|------------------------------------|
| `docker-registry-credentials`  | Username/Password  | Docker registry login              |
| `deploy-host-ip`               | Secret text        | Target server IP / hostname        |

---

## Metrics (Measured)

| Metric                      | Traditional              | Shared Library           | Improvement     |
|-----------------------------|--------------------------|--------------------------|------------------|
| Total lines per Jenkinsfile | 258                      | 19                       | **92.6%**       |
| Effective code lines        | 184                      | 7                        | **96.2%**       |
| Pipeline logic locations    | N repos (copy-paste)     | 1 centralized repo       | Centralized     |
| Time to onboard new app     | Hours                    | Minutes                  | **~90%**        |

> Both Jenkinsfiles are in `examples/` for side-by-side comparison.

---

## Testing

Run the Python validation unit tests locally (no Jenkins required):

```bash
# Run all 11 tests
python3 -m unittest tests.test_validate_env -v
```

| Test Category    | Count | Coverage |
|------------------|-------|----------|
| Happy path       | 1     | All vars present → pass |
| Failure paths    | 4     | Missing, empty, whitespace, single missing |
| Result structure | 3     | Keys, totals, arithmetic |
| Custom input     | 1     | Arbitrary var lists |
| Exit codes       | 2     | `sys.exit(0)` / `sys.exit(1)` |

---

## License

See [LICENSE](LICENSE) for details.
