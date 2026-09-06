variable "aws_region" {
  description = "AWS region for the platform."
  type        = string
  default     = "sa-east-1"
}

variable "project_name" {
  description = "Lowercase resource-name prefix."
  type        = string
  default     = "courtvision"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "project_name may contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "pilot"

  validation {
    condition     = contains(["staging", "pilot", "production"], var.environment)
    error_message = "environment must be staging, pilot, or production."
  }
}

variable "media_infrequent_access_after_days" {
  description = "Days before media moves from S3 Standard to Standard-IA."
  type        = number
  default     = 30
}

variable "media_archive_after_days" {
  description = "Days before media moves to Glacier Instant Retrieval."
  type        = number
  default     = 90
}

variable "media_max_retention_days" {
  description = "Global safety ceiling; application retention may delete media earlier."
  type        = number
  default     = 365
}
