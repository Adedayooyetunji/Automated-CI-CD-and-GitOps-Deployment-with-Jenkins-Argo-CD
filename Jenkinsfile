pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        AWS_REGION = 'eu-west-1'
        ECR_REPOSITORY = 'gitops-sample-app'
        GITOPS_REPO_URL = 'https://github.com/Adedayooyetunji/Automated-CI-CD-and-GitOps-Deployment-with-Jenkins-Argo-CD.git'
        GITOPS_BRANCH = 'gitops/auto'
        GITOPS_CREDENTIALS_ID = 'gitops-write'
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
                sh 'trivy fs --scanners vuln,misconfig,secret --exit-code 1 --severity HIGH,CRITICAL .'
            }
        }

        stage('Build, scan, and push image') {
            when {
                allOf {
                    branch 'main'
                    expression { env.APP_CHANGED == 'true' }
                }
            }
            steps {
                script {
                    env.IMAGE_TAG = env.GIT_COMMIT.take(12)
                    def accountId = sh(
                        script: 'aws sts get-caller-identity --query Account --output text',
                        returnStdout: true
                    ).trim()
                    env.IMAGE_URI = "${accountId}.dkr.ecr.${env.AWS_REGION}.amazonaws.com/${env.ECR_REPOSITORY}"
                }
                sh '''
                    aws ecr get-login-password --region "$AWS_REGION" |
                        docker login --username AWS --password-stdin \
                        "$(printf '%s' "$IMAGE_URI" | cut -d/ -f1)"
                    EXISTING_DIGEST="$(aws ecr batch-get-image \
                        --repository-name "$ECR_REPOSITORY" \
                        --image-ids "imageTag=$IMAGE_TAG" \
                        --query 'images[0].imageId.imageDigest' --output text)"
                    if [ "$EXISTING_DIGEST" = "None" ]; then
                        docker build --build-arg "APP_VERSION=$IMAGE_TAG" \
                            -t "$IMAGE_URI:$IMAGE_TAG" app
                        trivy image --exit-code 1 --severity HIGH,CRITICAL "$IMAGE_URI:$IMAGE_TAG"
                        docker push "$IMAGE_URI:$IMAGE_TAG"
                    else
                        docker pull "$IMAGE_URI:$IMAGE_TAG"
                        trivy image --exit-code 1 --severity HIGH,CRITICAL "$IMAGE_URI:$IMAGE_TAG"
                    fi
                '''
            }
        }

        stage('Update dev GitOps manifest') {
            when {
                allOf {
                    branch 'main'
                    expression { env.APP_CHANGED == 'true' }
                }
            }
            steps {
                withCredentials([gitUsernamePassword(
                    credentialsId: env.GITOPS_CREDENTIALS_ID,
                    gitToolName: 'Default'
                )]) {
                    sh '''
                        git remote set-url origin "$GITOPS_REPO_URL"
                        git fetch origin \
                            "+refs/heads/$GITOPS_BRANCH:refs/remotes/origin/$GITOPS_BRANCH"
                        git checkout -B "$GITOPS_BRANCH" "origin/$GITOPS_BRANCH"
                        cd gitops-config/overlays/dev
                        kustomize edit set image "sample-app=$IMAGE_URI:$IMAGE_TAG"
                        cd ../../..
                        git add gitops-config/overlays/dev/kustomization.yaml
                        if ! git diff --cached --quiet; then
                            git config user.name "Jenkins"
                            git config user.email "jenkins@users.noreply.github.com"
                            git commit -m "Deploy dev image $IMAGE_TAG"
                            git push origin "HEAD:refs/heads/$GITOPS_BRANCH"
                        fi
                    '''
                }
            }
        }
    }
}
