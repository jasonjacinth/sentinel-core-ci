/**
 * deployApp.groovy
 *
 * Modular deployment step. Deploys the containerized application
 * to the target environment via SSH (or a custom deploy command).
 *
 * Parameters:
 *   appName      (String) — application name
 *   appPort      (int)    — port the app listens on
 *   imageName    (String) — full image name (registry/repo)
 *   imageTag     (String) — image tag
 *   deployEnv    (String) — target environment (staging, production, etc.)
 *   deployTarget (String) — container / service name on the target host
 *   deployCmd    (String) — optional: full custom deploy command override
 */

def call(Map config = [:]) {
    def appName      = config.appName      ?: error('deployApp: appName is required')
    def appPort      = config.appPort      ?: 8080
    def imageName    = config.imageName    ?: error('deployApp: imageName is required')
    def imageTag     = config.imageTag     ?: 'latest'
    def deployEnv    = config.deployEnv    ?: 'staging'
    def deployTarget = config.deployTarget ?: "${appName}-${deployEnv}"
    def deployCmd    = config.deployCmd    ?: null

    def fullImage = "${imageName}:${imageTag}"

    echo "Deploying ${appName} to ${deployEnv}..."
    echo "   Image  : ${fullImage}"
    echo "   Target : ${deployTarget}"
    echo "   Port   : ${appPort}"

    if (deployCmd) {
        // Use the caller-supplied custom deploy command
        echo "   Using custom deploy command."
        sh "${deployCmd}"
    } else {
        // Default: SSH into DEPLOY_HOST and docker-run the new image
        withCredentials([
            string(credentialsId: 'deploy-host-ip', variable: 'DEPLOY_HOST')
        ]) {
            sh """
                ssh -o StrictHostKeyChecking=no deployer@\$DEPLOY_HOST << 'ENDSSH'
                    docker pull ${fullImage}
                    docker stop ${deployTarget} || true
                    docker rm   ${deployTarget} || true
                    docker run -d \\
                        --name ${deployTarget} \\
                        -p ${appPort}:${appPort} \\
                        --restart unless-stopped \\
                        ${fullImage}
                ENDSSH
            """
        }
    }

    echo "Deployment complete: ${appName}:${imageTag} -> ${deployEnv}"
}
