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
        stage('Start Local Scheduler') {
            steps {
                container("foundations-local-scheduler"){
                    sh "sh create_ci_config.sh"
                    sh "python3 -m local_docker_scheduler -p 5000 &"
                }
            }
        }
        stage('Run Tests') {
            steps {
                container("python3") {
                    sh './ci_install_requirements.sh'
                    sh 'python -m unittest test'
                }
            }
        }
    }
}