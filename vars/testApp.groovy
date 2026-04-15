/**
 * testApp.groovy
 *
 * Modular test step. Runs the application's test suite and
 * archives any JUnit/XML results found in the workspace.
 *
 * Parameters:
 *   appName    (String) — name of the application under test
 *   testCmd    (String) — shell command to run the test suite
 *   resultPath (String) — glob for test-result XML files (optional)
 */

def call(Map config = [:]) {
    def appName    = config.appName    ?: 'unknown-app'
    def testCmd    = config.testCmd    ?: './gradlew test'
    def resultPath = config.resultPath ?: '**/build/test-results/**/*.xml'

    echo "Running tests for ${appName}..."
    echo "   Command: ${testCmd}"

    sh "${testCmd}"

    // Archive test results if they exist (non-fatal if missing)
    echo "Looking for test results at: ${resultPath}"
    junit allowEmptyResults: true, testResults: "${resultPath}"

    echo "Tests completed for ${appName}"
}
