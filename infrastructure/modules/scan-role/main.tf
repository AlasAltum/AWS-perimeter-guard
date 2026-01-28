# ============================================
# IAM Role Module for Target Accounts
# ============================================
# This module creates an IAM role that can be assumed by the central account's Lambda function

variable "central_account_id" {
  description = "AWS account ID of the central account where Lambda runs"
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.central_account_id))
    error_message = "Central account ID must be a 12-digit number"
  }
}

variable "role_name" {
  description = "Name of the IAM role to create"
  type        = string
  default     = "perimeter-guard-scan-role"
}

variable "external_id" {
  description = "External ID for additional security (REQUIRED). Must match the value used in central account."
  type        = string
  
  validation {
    condition     = length(var.external_id) >= 16
    error_message = "External ID must be at least 16 characters for security"
  }
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# IAM Role that trusts the central account
resource "aws_iam_role" "scan_role" {
  name        = var.role_name
  description = "Allows central account Lambda to scan this account for WAF associations"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.central_account_id}:root"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "sts:ExternalId" = var.external_id
          }
        }
      }
    ]
  })

  tags = merge(var.common_tags, {
    Name           = var.role_name
    Purpose        = "AWS Perimeter Guard Scanner"
    CentralAccount = var.central_account_id
  })
}

# IAM Policy with permissions for WAF scanning
resource "aws_iam_role_policy" "scan_policy" {
  name = "PerimeterGuardScanPolicy"
  role = aws_iam_role.scan_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WAFv2ReadAccess"
        Effect = "Allow"
        Action = [
          "wafv2:ListWebACLs",
          "wafv2:GetWebACL",
          "wafv2:ListResourcesForWebACL",
          "wafv2:GetWebACLForResource"
        ]
        Resource = "*"
      },
      {
        Sid    = "LoadBalancerReadAccess"
        Effect = "Allow"
        Action = [
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:DescribeLoadBalancerAttributes",
          "elasticloadbalancing:DescribeTags"
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudFrontReadAccess"
        Effect = "Allow"
        Action = [
          "cloudfront:ListDistributions",
          "cloudfront:GetDistribution",
          "cloudfront:GetDistributionConfig"
        ]
        Resource = "*"
      },
      {
        Sid    = "APIGatewayReadAccess"
        Effect = "Allow"
        Action = [
          "apigateway:GET"
        ]
        Resource = [
          "arn:aws:apigateway:*::/restapis",
          "arn:aws:apigateway:*::/restapis/*/stages",
          "arn:aws:apigateway:*::/apis",
          "arn:aws:apigateway:*::/apis/*/stages"
        ]
      },
      {
        Sid    = "AppSyncReadAccess"
        Effect = "Allow"
        Action = [
          "appsync:ListGraphqlApis",
          "appsync:GetGraphqlApi"
        ]
        Resource = "*"
      },
      {
        Sid    = "CognitoReadAccess"
        Effect = "Allow"
        Action = [
          "cognito-idp:ListUserPools",
          "cognito-idp:DescribeUserPool"
        ]
        Resource = "*"
      },
      {
        Sid    = "AppRunnerReadAccess"
        Effect = "Allow"
        Action = [
          "apprunner:ListServices",
          "apprunner:DescribeService"
        ]
        Resource = "*"
      },
      {
        Sid    = "VerifiedAccessReadAccess"
        Effect = "Allow"
        Action = [
          "ec2:DescribeVerifiedAccessInstances",
          "ec2:DescribeVerifiedAccessInstanceWebAclAssociations"
        ]
        Resource = "*"
      }
    ]
  })
}

# Outputs
output "role_arn" {
  description = "ARN of the created IAM role"
  value       = aws_iam_role.scan_role.arn
}

output "role_name" {
  description = "Name of the created IAM role"
  value       = aws_iam_role.scan_role.name
}

output "external_id" {
  description = "External ID used for assuming the role"
  value       = var.external_id
}
