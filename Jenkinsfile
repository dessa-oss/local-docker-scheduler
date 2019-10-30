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
        stage('Setup Environment'){
            steps {
                container("python3") {
                    sh "./docker/setup_filesystem.sh"
                }
            }
        }
        stage('Install Test Requirements') {
            steps {
                container("python3") {
                    
                    sh './ci_install_requirements.sh'                    
                }
            }
        }
        stage('Run All Test') {
            steps {
                container("python3") {
                    sh 'python -m unittest test -f'
                }
            }
        }
        stage('Build and Push Scheduler Package Image') {
            steps {
                container("python3") {
                    ws("${WORKSPACE}/foundations_model_package/src"){
                        sh 'docker login docker.shehanigans.net -u $NEXUS_USER -p $NEXUS_PASSWORD'
                        sh './build_and_push.sh'
                    }
                }
            }
        }
    }
    post {
        failure {
            script {
                def output_logs = String.join('\n', currentBuild.rawBuild.getLog(200))
                def attachments = [
                    [
                        pretext: '@channel Build failed for `' + env.JOB_NAME + '` please visit ' + env.BUILD_URL + ' for more details.',
                        text: output_logs,
                        fallback: '@channel Build failed for `' + env.JOB_NAME + '` please visit ' + env.BUILD_URL + ' for more details.',
                        color: '#FF0000'
                    ]
                ]

                slackSend(channel: '#f9s-builds', attachments: attachments)
            }
        }
        success {
            slackSend color: '#00FF00', message: 'Build succeeded for `' + env.JOB_NAME + '` please visit ' + env.BUILD_URL + ' for more details.'
        }
    }
}