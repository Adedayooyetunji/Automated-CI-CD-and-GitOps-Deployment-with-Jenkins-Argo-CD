variable "aws_region" {
  description = "AWS region in which to create the cluster and ECR repository."
  type        = string
  default     = "eu-west-1"
}

variable "cluster_name" {
  description = "Name of the EKS cluster."
  type        = string
  default     = "gitops-eks"
}

variable "cluster_version" {
  description = "Kubernetes version supported by EKS in the selected region."
  type        = string
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "CIDR blocks allowed to reach the public Kubernetes API endpoint. Set to your current public IP /32."
  type        = list(string)

  validation {
    condition     = length(var.cluster_endpoint_public_access_cidrs) > 0
    error_message = "Specify at least one trusted CIDR; do not expose the Kubernetes API to the whole internet."
  }
}

variable "node_instance_types" {
  description = "EC2 instance types for the managed worker node group."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_desired_size" {
  description = "Initial desired EC2 worker count."
  type        = number
  default     = 2
}
