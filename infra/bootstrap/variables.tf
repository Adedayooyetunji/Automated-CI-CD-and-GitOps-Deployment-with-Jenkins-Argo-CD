variable "aws_region" {
  description = "AWS region for the Terraform state bucket."
  type        = string
  default     = "eu-west-1"
}

variable "bucket_name" {
  description = "Globally unique name for the Terraform state bucket."
  type        = string

  validation {
    condition     = length(var.bucket_name) >= 3 && length(var.bucket_name) <= 63
    error_message = "The S3 bucket name must be between 3 and 63 characters."
  }
}
