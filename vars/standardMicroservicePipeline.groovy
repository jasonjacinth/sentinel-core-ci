/**
 * standardMicroservicePipeline.groovy
 *
 * Master wrapper that orchestrates a full CI/CD pipeline for microservices.
 * Consumer Jenkinsfiles call this single function with a configuration map
 * to get a complete build → test → containerize → deploy workflow.
 *
 * Usage (in a consumer Jenkinsfile):
 *   @Library('jenkins-shared-lib') _
 *   standardMicroservicePipeline(
 *       appName:       'my-service',
 *       appPort:        8080,
 *       deployEnv:     'staging',
 *       dockerRegistry: 'registry.example.com'
 *   )
 */

def call(Map config = [:]) {

    // -------------------------------------------------------------------------
    // 1. Validate required configuration keys
    // -------------------------------------------------------------------------
    def requiredKeys = ['appName', 'appPort', 'deployEnv', 'dockerRegistry']
    def missingKeys  = requiredKeys.findAll { !config.containsKey(it) }

    if (missingKeys) {
        error "standardMicroservicePipeline: Missing required config keys: ${missingKeys}"
    }

    // -------------------------------------------------------------------------
    // 2. Derive sensible defaults
    // -------------------------------------------------------------------------
    def appName        = config.appName
    def appPort        = config.appPort
    def deployEnv      = config.deployEnv
    def dockerRegistry = config.dockerRegistry
    def imageName      = config.imageName      ?: "${dockerRegistry}/${appName}"
    def imageTag       = config.imageTag       ?: "${env.BUILD_NUMBER ?: 'latest'}"
    def buildCmd       = config.buildCmd       ?: './gradlew clean build'
    def testCmd        = config.testCmd        ?: './gradlew test'
    def dockerfilePath = config.dockerfilePath ?: 'Dockerfile'
    def deployTarget   = config.deployTarget   ?: "${appName}-${deployEnv}"
    def deployCmd      = config.deployCmd      ?: null   // optional override

    // -------------------------------------------------------------------------
    // 3. Declarative Pipeline
    // -------------------------------------------------------------------------
    pipeline {
        agent any

        environment {
            APP_NAME        = "${appName}"
            APP_PORT        = "${appPort}"
            DEPLOY_ENV      = "${deployEnv}"
            DOCKER_REGISTRY = "${dockerRegistry}"
            IMAGE_NAME      = "${imageName}"
            IMAGE_TAG       = "${imageTag}"
        }

        options {
            timestamps()
            timeout(time: 30, unit: 'MINUTES')
            buildDiscarder(logRotator(numToKeepStr: '10'))
        }

        stages {
            // -----------------------------------------------------------------
            // Stage 0 — Pre-flight Validation (Python)
            // -----------------------------------------------------------------
            stage('Pre-flight Validation') {
                steps {
                    script {
                        echo "Running pre-flight environment validation..."
                        def validationScript = libraryResource('scripts/validate_env.py')
                        writeFile file: 'validate_env.py', text: validationScript
                        sh 'python3 validate_env.py'
                    }
                }
            }

            // -----------------------------------------------------------------
            // Stage 1 — Build
            // -----------------------------------------------------------------
            stage('Build') {
                steps {
                    script {
                        buildApp(
                            appName:  appName,
                            buildCmd: buildCmd
                        )
                    }
                }
            }

            // -----------------------------------------------------------------
            // Stage 2 — Test
            // -----------------------------------------------------------------
            stage('Test') {
                steps {
                    script {
                        testApp(
                            appName: appName,
                            testCmd: testCmd
                        )
                    }
                }
            }

            // -----------------------------------------------------------------
            // Stage 3 — Build & Push Container Image
            // -----------------------------------------------------------------
            stage('Build & Push Container') {
                steps {
                    script {
                        buildAndPushContainer(
                            imageName:      imageName,
                            imageTag:       imageTag,
                            dockerfilePath: dockerfilePath,
                            dockerRegistry: dockerRegistry
                        )
                    }
                }
            }

            // -----------------------------------------------------------------
            // Stage 4 — Deploy
            // -----------------------------------------------------------------
            stage('Deploy') {
                steps {
                    script {
                        deployApp(
                            appName:      appName,
                            appPort:      appPort,
                            imageName:    imageName,
                            imageTag:     imageTag,
                            deployEnv:    deployEnv,
                            deployTarget: deployTarget,
                            deployCmd:    deployCmd
                        )
                    }
                }
            }
        }

        // ---------------------------------------------------------------------
        // Post-pipeline notifications
        // ---------------------------------------------------------------------
        post {
            success {
                echo "Pipeline SUCCESS: ${appName}:${imageTag} deployed to ${deployEnv}"
            }
            failure {
                echo "Pipeline FAILED: ${appName} on ${deployEnv}. Check logs above."
            }
            always {
                echo "Cleaning up workspace..."
                cleanWs()
            }
        }
    }
}
