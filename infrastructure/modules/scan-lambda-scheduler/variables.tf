# ============================================
# General Configuration
# ============================================

variable "aws_region" {
  description = "AWS region for Lambda deployment"
  type        = string
  default     = "us-east-1"
}

variable "scan_regions" {
  description = "List of AWS regions to scan (empty list = all enabled regions)"
  type        = list(string)
  default     = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "af-south-1",
    "ap-east-1",
    "ap-south-2",
    "ap-southeast-3",
    "ap-southeast-5",
    "ap-southeast-4",
    "ap-south-1",
    "ap-southeast-6",
    "ap-northeast-3",
    "ap-northeast-2",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-east-2",
    "ap-southeast-7",
    "ap-northeast-1",
    "ca-central-1",
    "ca-west-1",
    "eu-central-1",
    "eu-west-1",
    "eu-west-2",
    "eu-south-1",
    "eu-west-3",
    "eu-south-2",
    "eu-north-1",
    "eu-central-2",
    "il-central-1",
    "mx-central-1",
    "me-south-1",
    "me-central-1",
    "sa-east-1",
    "us-gov-east-1",
    "us-gov-west-1"
  ]
}

variable "scan_schedule" {
  description = "EventBridge schedule expression (rate or cron)"
  type        = string
  default     = "rate(24 hours)"
  
  validation {
    condition     = can(regex("^(rate|cron)\\(", var.scan_schedule))
    error_message = "Schedule must be a valid EventBridge expression (rate(...) or cron(...))"
  }
}

# ============================================
# Lambda Configuration
# ============================================

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 300
  
  validation {
    condition     = var.lambda_timeout >= 60 && var.lambda_timeout <= 900
    error_message = "Lambda timeout must be between 60 and 900 seconds"
  }
}

variable "lambda_memory_size" {
  description = "Lambda function memory size in MB. I recommend setting it to 256"
  type        = number
  default     = 256
  
  validation {
    condition     = var.lambda_memory_size >= 128 && var.lambda_memory_size <= 10240
    error_message = "Lambda memory size must be between 128 and 10240 MB"
  }
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention period in days"
  type        = number
  default     = 7
  
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Log retention must be a valid CloudWatch Logs retention value"
  }
}

# ============================================
# Multi-Account Configuration
# ============================================

variable "target_accounts" {
  description = "List of AWS account IDs to scan for WAF associations. The Lambda will assume a role in each account."
  type        = list(string)
  default     = []
  
  validation {
    condition     = alltrue([for id in var.target_accounts : can(regex("^[0-9]{12}$", id))])
    error_message = "All account IDs must be 12-digit numbers"
  }
}

variable "scan_role_name" {
  description = "Name of the IAM role to assume in target accounts (must be manually created in each account)"
  type        = string
  default     = "PerimeterGuardScanRole"
}

variable "external_id" {
  description = "External ID for cross-account role assumption (security feature). IMPORTANT: Use a strong random value (e.g., uuidgen output) to prevent confused deputy attacks."
  type        = string
  
  validation {
    condition     = length(var.external_id) >= 16
    error_message = "External ID must be at least 16 characters for security. Generate with: uuidgen or openssl rand -base64 32"
  }
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "lambda_source_dir" {
  description = "Absolute path to the Lambda source code directory. If not set, uses relative path from module."
  type        = string
  default     = ""
}
