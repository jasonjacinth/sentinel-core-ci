/**
 * buildApp.groovy
 *
 * Modular build step. Executes the application build command
 * (e.g. Gradle, Maven, npm) inside the workspace.
 *
 * Parameters:
 *   appName  (String) — name of the application being built
 *   buildCmd (String) — shell command to execute the build
 */

def call(Map config = [:]) {
    def appName  = config.appName  ?: 'unknown-app'
    def buildCmd = config.buildCmd ?: './gradlew clean build'

    echo "Building ${appName}..."
    echo "   Command: ${buildCmd}"

    sh "${buildCmd}"

    echo "Build completed for ${appName}"
}
