# Jenkins CI/CD on an Existing EC2 Instance

This project builds, tests, and scans a small Python web app, then deploys it as a Docker container on the same EC2 instance that runs the Jenkins build agent. It does not create AWS resources and does not use EKS, Argo CD, or an external image registry.

## Deployment flow

```text
GitHub main branch
       │ webhook
       ▼
Jenkins on the existing EC2 instance
       │
       ├── unit tests
       ├── Trivy source and image scans
       ├── Docker image tagged with the commit SHA
       └── health-checked Docker deployment on port 8081
```

Non-`main` branches run validation and build the image but do not deploy. A `main` build replaces the running container only after tests and scans pass. Jenkins checks Docker's container health after startup and attempts to restore the previous image if the check fails.

## Requirements

- An existing, running EC2 instance with enough free CPU, memory, and disk for Jenkins and Docker
- Jenkins installed and reachable, with a multibranch pipeline configured for this repository
- Jenkins Pipeline, Git, and GitHub plugins, plus a GitHub webhook to Jenkins
- Python 3, Docker Engine, Docker CLI, and Trivy available to the Jenkins build agent
- The Jenkins agent must run on this EC2 host and be allowed to use its Docker daemon

Do not expose Jenkins directly to the internet without appropriate access controls and TLS. Membership in the Docker group effectively grants root-level control of the host. Only allow trusted users to change pipeline code or trigger builds, and use a dedicated instance for this project.

## Configure the existing EC2 instance

1. In the AWS console, confirm the instance is running and note its public DNS/IP. This project does not start, resize, or otherwise modify the instance.
2. Install Jenkins, Docker Engine, and Trivy following the official instructions for the instance's operating system. The operating system and current instance configuration are not assumed by this repository.
3. Configure the Jenkins build agent to run on this same host and verify that the Jenkins agent user can run `docker version` and `docker run`.
4. Ensure port `8081` is available. If you want to access the app from your own network, allow inbound TCP `8081` only from your trusted IP/CIDR in the instance security group. Do not open it to the whole internet by default. For public production traffic, put a TLS-terminating reverse proxy or load balancer in front of it.
5. In Jenkins, create a multibranch pipeline pointing to this GitHub repository and enable GitHub webhook discovery. Add a webhook in the repository settings for your Jenkins GitHub webhook endpoint.

The pipeline uses no AWS API, AWS credentials, GitHub write token, ECR, or SSH deployment credential. Jenkins checks out the source with the repository's configured GitHub access. If the repository is private, configure read-only checkout credentials in Jenkins.

## Run a deployment

Push an application change to `main`. Jenkins will:

1. Run the Python unit tests.
2. Scan `app/` for high/critical findings with Trivy.
3. Build an image tagged with the 12-character Git commit SHA.
4. Scan the image for high/critical vulnerabilities.
5. On `main` only, replace the `gitops-sample-app` container and wait for its health check.

The application listens on port `8080` inside its container and port `8081` on the EC2 host:

- `http://<EC2-public-DNS-or-IP>:8081/` returns app, environment, and version information
- `/healthz` and `/readyz` return health status

To test locally without Jenkins:

```bash
cd app
python3 -m unittest discover -s tests -v
docker build --build-arg APP_VERSION=local -t gitops-sample-app:local .
docker run --rm -p 8081:8080 gitops-sample-app:local
```

Then open `http://localhost:8081/`.

## Operations

```bash
# Inspect deployment and health
docker ps --filter name=gitops-sample-app
docker inspect --format='{{.State.Health.Status}}' gitops-sample-app
docker logs --tail 100 gitops-sample-app

# Stop and remove the application container
docker rm --force gitops-sample-app
```

Jenkins deployment has a short interruption while replacing the single container. The previously used image remains locally available for rollback. Docker's `unless-stopped` restart policy starts the current container after an instance reboot; Jenkins itself should also be configured to start on boot.

## Security and cost

- No Terraform apply, AWS resource creation, or cloud deployment occurs in this project.
- EC2 compute, attached storage, and data transfer may still incur charges under your AWS account.
- Never commit credentials, private keys, `.pem` files, or Jenkins secrets.
- Restrict security-group ingress to the minimum required ports and trusted source IPs.
- Review Trivy findings instead of bypassing failed scans.
