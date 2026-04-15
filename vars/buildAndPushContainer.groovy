/**
 * buildAndPushContainer.groovy
 *
 * Builds a Docker image from the workspace Dockerfile and pushes it
 * to the configured container registry.
 *
 * Parameters:
 *   imageName      (String) — full image name (registry/repo)
 *   imageTag       (String) — tag for the image (e.g. build number)
 *   dockerfilePath (String) — path to the Dockerfile
 *   dockerRegistry (String) — registry URL for docker login
 */

def call(Map config = [:]) {
    def imageName      = config.imageName      ?: error('buildAndPushContainer: imageName is required')
    def imageTag       = config.imageTag       ?: 'latest'
    def dockerfilePath = config.dockerfilePath ?: 'Dockerfile'
    def dockerRegistry = config.dockerRegistry ?: error('buildAndPushContainer: dockerRegistry is required')

    def fullImage = "${imageName}:${imageTag}"

    echo "Building container image: ${fullImage}"
    echo "   Dockerfile: ${dockerfilePath}"

    sh "docker build -t ${fullImage} -f ${dockerfilePath} ."

    echo "Pushing ${fullImage} to ${dockerRegistry}..."

    // Authenticate using credentials injected as DOCKER_USER / DOCKER_PASS
    withCredentials([
        usernamePassword(
            credentialsId: 'docker-registry-credentials',
            usernameVariable: 'DOCKER_USER',
            passwordVariable: 'DOCKER_PASS'
        )
    ]) {
        sh "echo \$DOCKER_PASS | docker login ${dockerRegistry} -u \$DOCKER_USER --password-stdin"
        sh "docker push ${fullImage}"
    }

    echo "Image pushed: ${fullImage}"
}
