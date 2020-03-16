def build_number = env.BUILD_URL
def customMetrics = [:]
def customMetricsMap = [:]

pipeline{
    agent {
        label 'ci-pipeline-jenkins-slave'
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
                    sh 'pip install -r requirements_dev.txt'
                }
            }
        }
        stage('Run All Test') {
            steps {
                container("python3") {
                    sh 'python -m unittest -v -f test'
                }
            }
        }
        stage('Build Scheduler Image') {
            steps {
                container("python3") {
                    sh 'NEXUS_DOCKER_REGISTRY=${NEXUS_DOCKER_STAGING}/foundations ./build_image.sh'
                }
            }
        }
        stage('Push Scheduler Image') {
            steps {
                container("python3") {
                    sh 'docker login $NEXUS_DOCKER_STAGING -u $NEXUS_USER -p $NEXUS_PASSWORD'
                    sh 'NEXUS_DOCKER_REGISTRY=${NEXUS_DOCKER_STAGING}/foundations ./push_image.sh'
                }
            }
        }
        stage('Trigger Build Artifacts for Atlas Pipeline') {
            steps {
                container("python3") {
                    script {
                        echo "Triggering job for building Atlas Artifacts"
                        version = sh(script: 'python get_version.py', returnStdout: true).trim()
                        println("Attempting to trigger pipeline with version of ${version}")
                        build job: "build-installer-atlas", wait: false, parameters: [
                            [$class: 'StringParameterValue', name: 'scheduler', value: "${NEXUS_DOCKER_STAGING}/foundations/scheduler:${version}"]
                        ]
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
                slackSend(channel: '#dessa-atlas-builds', attachments: attachments)
            }
        }
        success {
            slackSend color: '#00FF00', message: 'Build succeeded for `' + env.JOB_NAME + '` please visit ' + env.BUILD_URL + ' for more details.'
        }
    }
}