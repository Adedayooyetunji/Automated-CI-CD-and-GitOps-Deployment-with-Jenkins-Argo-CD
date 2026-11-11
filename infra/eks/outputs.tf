output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "cluster_region" {
  description = "AWS region containing the EKS cluster."
  value       = var.aws_region
}

output "ecr_repository_url" {
  description = "Private ECR URL for the application image."
  value       = aws_ecr_repository.app.repository_url
}
