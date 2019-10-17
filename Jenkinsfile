def build_number = env.BUILD_URL
def customMetrics = [:]
def customMetricsMap = [:]

pipeline{
    agent {
        label 'ci-pipeline-jenkins-atlas-ce'
    }

    stages {
        stage('Preparation') {
            steps {
                script {
                    customMetricsMap["jenkins_data"] = customMetrics
                    checkout scm
                }
            }
        }
        stage('Run Tests') {
            steps {
                container("python3") {
                    sh './ci_install_requirements'
                    sh 'python -m unittest test'
                }
            }
        }
    }
}