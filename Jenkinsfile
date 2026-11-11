pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        APP_IMAGE = 'gitops-sample-app'
        APP_CONTAINER = 'gitops-sample-app'
        APP_PORT = '8081'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Detect application changes') {
            steps {
                script {
                    if (env.GIT_PREVIOUS_SUCCESSFUL_COMMIT) {
                        def changedFiles = sh(
                            script: 'git diff --name-only "$GIT_PREVIOUS_SUCCESSFUL_COMMIT" "$GIT_COMMIT" -- app',
                            returnStdout: true
                        ).trim()
                        env.APP_CHANGED = changedFiles ? 'true' : 'false'
                    } else {
                        env.APP_CHANGED = 'true'
                    }
                    echo "Application files changed: ${env.APP_CHANGED}"
                }
            }
        }

        stage('Test') {
            when {
                expression { env.APP_CHANGED == 'true' }
            }
            steps {
                dir('app') {
                    sh 'python3 -m unittest discover -s tests -v'
                }
            }
        }

        stage('Scan source') {
            when {
                expression { env.APP_CHANGED == 'true' }
            }
            steps {
                sh 'trivy fs --scanners vuln,misconfig,secret --exit-code 1 --severity HIGH,CRITICAL app'
            }
        }

        stage('Build and scan image') {
            when {
                expression { env.APP_CHANGED == 'true' }
            }
            steps {
                script {
                    env.IMAGE_TAG = env.GIT_COMMIT.take(12)
                }
                sh '''
                    docker build --build-arg "APP_VERSION=$IMAGE_TAG" \
                        -t "$APP_IMAGE:$IMAGE_TAG" app
                    trivy image --exit-code 1 --severity HIGH,CRITICAL "$APP_IMAGE:$IMAGE_TAG"
                '''
            }
        }

        stage('Deploy on EC2') {
            when {
                allOf {
                    branch 'main'
                    expression { env.APP_CHANGED == 'true' }
                }
            }
            steps {
                sh '''
                    set -eu
                    previous_image="$(docker inspect --format='{{.Config.Image}}' "$APP_CONTAINER" 2>/dev/null || true)"

                    docker rm --force "$APP_CONTAINER" >/dev/null 2>&1 || true
                    docker run --detach \
                        --name "$APP_CONTAINER" \
                        --restart unless-stopped \
                        --publish "$APP_PORT:8080" \
                        --env APP_ENV=prod \
                        "gitops-sample-app:$IMAGE_TAG"

                    attempt=0
                    while [ "$attempt" -lt 30 ]; do
                        status="$(docker inspect --format='{{.State.Health.Status}}' "$APP_CONTAINER" 2>/dev/null || printf 'missing')"
                        if [ "$status" = "healthy" ]; then
                            echo "Deployed $APP_IMAGE:$IMAGE_TAG on port $APP_PORT"
                            exit 0
                        fi
                        if [ "$status" = "unhealthy" ] || [ "$status" = "missing" ]; then
                            break
                        fi
                        attempt=$((attempt + 1))
                        sleep 2
                    done

                    docker logs "$APP_CONTAINER" || true
                    docker rm --force "$APP_CONTAINER" >/dev/null 2>&1 || true
                    if [ -n "$previous_image" ]; then
                        echo "Deployment health check failed; restoring $previous_image"
                        docker run --detach \
                            --name "$APP_CONTAINER" \
                            --restart unless-stopped \
                            --publish "$APP_PORT:8080" \
                            --env APP_ENV=prod \
                            "$previous_image"
                    fi
                    exit 1
                '''
            }
        }
    }
}
