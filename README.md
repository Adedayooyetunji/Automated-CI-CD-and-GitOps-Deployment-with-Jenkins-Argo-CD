# Automated CI/CD and GitOps Deployment with Jenkins & Argo CD

A working starter project for building a small Python web app, testing and scanning it with Jenkins, publishing immutable images to Amazon ECR, and deploying them to Amazon EKS through Argo CD and Kustomize.

## How it works

```text
GitHub main branch
       │ webhook
       ▼
Jenkins ── tests + Trivy scans ── Docker build/push ──▶ Amazon ECR
       │                                               │
       └── commits dev image tag to gitops/auto ───────┘
                           │
                           ▼
                    Argo CD ApplicationSets
                           │
                   Kustomize overlays
                 dev / staging / prod namespaces
                           │
                           ▼
                       Amazon EKS
```

Jenkins handles CI: it tests the app, scans source and the built image, pushes an image tagged with the source commit, and updates the dev image reference in Git. Argo CD handles CD: it watches the `gitops/auto` branch and reconciles the cluster to the manifests in Git. Dev and staging sync automatically; production requires an explicit sync. Promote staging and production by pull request, changing their image tags to an already-published commit SHA.

The app and infrastructure live in this repository. A dedicated `gitops/auto` branch holds the deployment configuration that Argo CD watches. This keeps Jenkins deployment commits off `main` and prevents them from triggering the application build. For stronger organizational isolation, move `gitops-config/` into a separate private/public GitOps repository and update the Jenkinsfile and ApplicationSet repository URLs.

## Repository layout

```text
app/                         Python HTTP app, tests, and Dockerfile
Jenkinsfile                  Declarative Jenkins pipeline
infra/
  bootstrap/                 Encrypted, versioned S3 Terraform state bucket
  eks/                       VPC, EKS, ECR, and remote-state configuration
gitops-config/
  base/                      Kubernetes Deployment and Service
  overlays/{dev,staging,prod}/ Environment-specific Kustomize settings
  applicationset.yaml        Argo CD ApplicationSets for all environments
```

## Prerequisites

- An AWS account and AWS CLI v2 configured with an IAM role or SSO profile
- Terraform 1.10+, Git, Docker, `kubectl`, and Kustomize
- A GitHub account with write access to this repository
- Jenkins with the Pipeline, Git, GitHub, and Credentials Binding plugins
- A Jenkins agent with Python 3, Docker, AWS CLI v2, Trivy, and Kustomize installed

Terraform provisions AWS resources, but does not create or install Jenkins. Run Jenkins on a separately managed host/service with a narrowly scoped IAM role. EKS, NAT gateways, and EC2 nodes incur ongoing charges; review the plan and your AWS pricing before applying it.

## 1. Create the Terraform state bucket

In PowerShell, configure an AWS profile and region, then verify the identity before continuing:

```powershell
$env:AWS_PROFILE = "gitops"
$env:AWS_REGION = "eu-west-1"
aws sso login --profile $env:AWS_PROFILE
aws sts get-caller-identity

Set-Location infra\bootstrap
terraform init
terraform apply -var="bucket_name=replace-with-a-globally-unique-name" -var="aws_region=$env:AWS_REGION"
```

The state bucket enables versioning, server-side encryption, public-access blocking, and object ownership controls. Its Terraform resource has `prevent_destroy`; retain it while any state uses the bucket.

## 2. Provision EKS and ECR

Restrict the Kubernetes API endpoint to your current public IP in CIDR notation (for example, `203.0.113.10/32`). Do not use `0.0.0.0/0`. Set an EKS Kubernetes version currently supported in your chosen AWS region.

```powershell
Set-Location ..\eks
Copy-Item backend.hcl.example backend.hcl
Copy-Item terraform.tfvars.example terraform.tfvars
```

Edit `backend.hcl` to set the bucket name created in step 1. Edit `terraform.tfvars` to set your trusted API CIDR and a currently supported Kubernetes version, then run:

```powershell
terraform init -backend-config=backend.hcl
terraform validate
terraform plan
terraform apply

$cluster = terraform output -raw cluster_name
$region = terraform output -raw cluster_region
aws eks update-kubeconfig --name $cluster --region $region
kubectl get nodes
Set-Location ..\..
```

The EKS module creates a VPC with private worker subnets and a single NAT gateway, a managed node group, and an immutable-tag ECR repository. A single NAT gateway reduces cost but is not highly available. The cluster creator receives cluster-admin access; the EKS API is reachable only from the CIDRs you specify.

## 3. Prepare the GitOps branch and Jenkins

Create the branch Argo CD will watch:

```powershell
git push origin main:gitops/auto
```

Create a Jenkins multibranch pipeline for this repository and configure it to build `main`. Add a GitHub webhook for the Jenkins GitHub endpoint, then configure:

- A Jenkins credential with ID `gitops-write`, type **Username with password**, using a GitHub identity/token with repository contents write permission. Do not put tokens in the Jenkinsfile.
- An IAM role for the Jenkins agent with ECR login and push permissions limited to this repository, plus `sts:GetCallerIdentity`. Prefer an instance/workload role over AWS access keys.
- The `AWS_REGION` value in the Jenkinsfile to match the Terraform region if it is not `eu-west-1`.
- The Jenkins agent tools listed in Prerequisites. Docker must be available to the build agent.

The Jenkinsfile tests and scans only changes under `app/`. On a `main` build it tags the image with the Git commit SHA, scans and pushes it, then commits the dev image update to `gitops/auto`. Jenkins must be able to push to that branch; if branch rules require pull requests, adapt the final stage to open a PR instead.

## 4. Build the first image and promote it

Push an application change to `main` and confirm Jenkins succeeds. It should update `gitops-config/overlays/dev/kustomization.yaml` with the ECR image URI and immutable commit tag.

Before creating Argo CD applications, promote that same valid image to staging and production so those overlays do not reference the example placeholder:

```powershell
git checkout -b promote/initial-image origin/gitops/auto
$image = "123456789012.dkr.ecr.eu-west-1.amazonaws.com/gitops-sample-app:0123456789ab"
Set-Location gitops-config\overlays\staging
kustomize edit set image "sample-app=$image"
Set-Location ..\prod
kustomize edit set image "sample-app=$image"
Set-Location ..\..\..
git add gitops-config
git commit -m "Promote initial image to staging and prod"
git push -u origin promote/initial-image
```

Replace the example `$image` URI and tag with `terraform output -raw ecr_repository_url` and the image tag from the successful Jenkins build. Open and merge a pull request into `gitops/auto`. Subsequent releases follow the same PR process: promote the tested SHA to staging, then to prod when approved.

## 5. Install Argo CD and connect the cluster

Install Argo CD in the cluster and retrieve its initial password. Use a current, reviewed Argo CD release manifest rather than relying on an unreviewed deployment source:

```powershell
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" |
  ForEach-Object { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Review the repository URL and target branch in `gitops-config/applicationset.yaml` if you forked or renamed this project. Apply the ApplicationSets:

```powershell
kubectl apply -f gitops-config\applicationset.yaml
kubectl get applications -n argocd
```

The `dev` and `staging` applications sync automatically, with pruning and self-healing. The `prod` application does not auto-sync; sync it in the Argo CD UI/CLI after approval. Keep the initial admin password private and replace it with managed Argo CD accounts/SSO before production use.

## App endpoints

The sample app listens on port `8080`:

- `/` returns JSON with the app, environment, and image version
- `/healthz` and `/readyz` provide Kubernetes health probes

The Kubernetes Service is internal (`ClusterIP`); no public ingress or load balancer is created.

## Cleanup and costs

EKS control planes, EC2 nodes, EBS volumes, and NAT gateways can continue billing while running. Delete the Argo CD-managed applications first, then destroy the EKS stack:

```powershell
kubectl delete applicationset sample-app-nonprod sample-app-prod -n argocd
Set-Location infra\eks
terraform destroy -var-file=terraform.tfvars
```

The Terraform backend bucket is intentionally protected from destruction. Only after retiring the project and any state stored in it should you remove its `prevent_destroy` lifecycle rule and destroy the bucket.

## Troubleshooting

| Symptom | Check |
|---|---|
| `ExpiredToken` | Refresh the AWS SSO session with `aws sso login --profile gitops`. |
| EKS endpoint timeout | Confirm your public IP is in `cluster_endpoint_public_access_cidrs`. |
| Jenkins cannot push | Check the `gitops-write` credential, branch permissions, and `gitops/auto` branch. |
| `ImagePullBackOff` | Verify the ECR URI/tag in the overlay and node-group ECR pull access. |
| Argo CD `OutOfSync` or app missing | Check the ApplicationSet repository URL, `gitops/auto` branch, and overlay path. |
| Trivy blocks a build | Review the reported high/critical issue and update the affected dependency or base image before retrying. |

## Security notes

- Never commit AWS credentials, GitHub tokens, kubeconfigs, Terraform state, or `.tfvars` files.
- The Kubernetes API CIDR variable is required and has no open-to-the-world default.
- Images use immutable commit-SHA tags; ECR scans on push and expires older images.
- Containers run as a non-root user with a read-only root filesystem and resource limits.
- Review Terraform plans and image scan findings before applying or promoting changes.
