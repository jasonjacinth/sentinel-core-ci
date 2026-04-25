# Sentinel Core CI -- Microservice Pipeline Templates

A centralized Sentinel Core CI library that standardizes CI/CD workflows across application teams. Complex pipeline logic is abstracted into a single declarative wrapper, paired with Python-based pre-flight and post-deploy validation to ensure environment integrity and deployment health.

---

## Repository Structure

```text
sentinel-core-ci/
├── vars/
│   ├── standardMicroservicePipeline.groovy   # Main pipeline wrapper
│   ├── buildApp.groovy                       # Build stage
│   ├── testApp.groovy                        # Test stage
│   ├── buildAndPushContainer.groovy          # Container build & push
│   └── deployApp.groovy                      # Deployment stage
├── resources/
│   └── scripts/
│       ├── validate_env.py                   # Pre-flight env validation
│       └── verify_deploy.py                  # Post-deploy verification
├── tests/
│   ├── test_validate_env.py                  # Pre-flight tests (11 tests)
│   └── test_verify_deploy.py                 # Post-deploy tests (18 tests)
├── examples/
│   ├── Jenkinsfile                           # Optimized consumer (<20 lines)
│   └── Jenkinsfile.traditional               # Traditional comparison (304 lines)
├── src/                                      # Reserved for future use
└── README.md
```

---

## Quick Start

### 1. Register the Library in Jenkins

Go to **Manage Jenkins → System → Global Pipeline Libraries** and add:

| Field              | Value                                          |
|--------------------|------------------------------------------------|
| **Name**           | `sentinel-core-ci`                             |
| **Default Version**| `main`                                         |
| **Retrieval**      | Modern SCM → Git                               |
| **Project URL**    | `https://github.com/<org>/sentinel-core-ci`    |

### 2. Create a Consumer Jenkinsfile

In the root of your application repository, create a `Jenkinsfile`:

```groovy
@Library('sentinel-core-ci') _

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

## Post-deploy Verification

The Python verification script (`resources/scripts/verify_deploy.py`) runs as the **final pipeline stage** after deployment. It confirms the newly deployed container is healthy before the pipeline reports success.

### Checks Performed

| Check              | Method                          | Pass Condition                |
|--------------------|---------------------------------|-------------------------------|
| Environment vars   | `os.environ` lookup             | All 4 required vars set       |
| Container status   | SSH + `docker inspect`          | Container state is "running"  |
| HTTP health probe  | `GET /health` via `urllib`      | HTTP 200 response             |

### Variables Required

| Variable      | Description                              |
|---------------|------------------------------------------|
| `APP_NAME`    | Application / service name               |
| `APP_PORT`    | Port the application listens on          |
| `DEPLOY_ENV`  | Target deployment environment            |
| `DEPLOY_HOST` | Target host IP or hostname               |

If any check fails, the script exits with code `1` and the pipeline **reports a failed deployment**.

### Local Testing

```bash
# All vars set (requires SSH access and a running container)
APP_NAME=order-service APP_PORT=8080 DEPLOY_ENV=staging DEPLOY_HOST=10.0.0.1 \
python3 resources/scripts/verify_deploy.py

# No vars set -> should fail with exit code 1
python3 resources/scripts/verify_deploy.py
```

---

## Pipeline Stages

```text
┌──────────────────────────┐
│  Pre-flight Validation   │  <- validate_env.py
└────────────┬─────────────┘
             v
┌──────────────────────────┐
│          Build           │  <- buildApp.groovy
└────────────┬─────────────┘
             v
┌──────────────────────────┐
│          Test            │  <- testApp.groovy
└────────────┬─────────────┘
             v
┌──────────────────────────┐
│   Build & Push Image     │  <- buildAndPushContainer.groovy
└────────────┬─────────────┘
             v
┌──────────────────────────┐
│         Deploy           │  <- deployApp.groovy
└────────────┬─────────────┘
             v
┌──────────────────────────┐
│ Post-deploy Verification │  <- verify_deploy.py
└──────────────────────────┘
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
| Total lines per Jenkinsfile | 304                      | 19                       | **93.8%**       |
| Effective code lines        | 218                      | 7                        | **96.8%**       |
| Pipeline logic locations    | N repos (copy-paste)     | 1 centralized repo       | Centralized     |
| Time to onboard new app     | Hours                    | Minutes                  | **~90%**        |

> Both Jenkinsfiles are in `examples/` for side-by-side comparison.

---

## Testing

Run all unit tests locally (no Jenkins required):

```bash
# Run pre-flight validation tests (11 tests)
python3 -m unittest tests.test_validate_env -v

# Run post-deploy verification tests (18 tests)
python3 -m unittest tests.test_verify_deploy -v
```

### Pre-flight Validation Tests (test_validate_env.py)

| Test Category    | Count | Coverage |
|------------------|-------|----------|
| Happy path       | 1     | All vars present -> pass |
| Failure paths    | 4     | Missing, empty, whitespace, single missing |
| Result structure | 3     | Keys, totals, arithmetic |
| Custom input     | 1     | Arbitrary var lists |
| Exit codes       | 2     | `sys.exit(0)` / `sys.exit(1)` |

### Post-deploy Verification Tests (test_verify_deploy.py)

| Test Category       | Count | Coverage |
|---------------------|-------|----------|
| Env var checking    | 4     | All present, all missing, single missing, whitespace |
| Container checks    | 4     | Running, exited, SSH failure, timeout |
| Health probes       | 3     | HTTP 200, HTTP 503, unreachable |
| Verify orchestrator | 5     | All pass, env skip, container down, keys, arithmetic |
| Exit codes          | 2     | `sys.exit(0)` / `sys.exit(1)` |

---

## License

See [LICENSE](LICENSE) for details.
