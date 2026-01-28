# ============================================
# Local Values
# ============================================

locals {
  lambda_name = "perimeter-guard-scanner"
  
  # Get current account ID
  central_account_id = data.aws_caller_identity.current.account_id
}

# Get current account identity
data "aws_caller_identity" "current" {}

# ============================================
# Lambda Function (using official module)
# ============================================

module "lambda_function" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "8.2.0"

  function_name = local.lambda_name
  description   = "Scans AWS resources for WAF associations across multiple accounts"
  handler       = "src.adapters.inbound.lambda_handler.handler"
  runtime       = "python3.12"
  
  # Package only the src directory (path relative to infrastructure/modules/scan-lambda-scheduler)
  source_path = [
    {
      path          = "${path.module}/../../../src"
      prefix_in_zip = "src"
      excludes      = [
        "adapters/inbound/cli_adapter.py",
        "main.py"
      ]
    }
  ]
  
  timeout     = var.lambda_timeout
  memory_size = var.lambda_memory_size
  
  # CloudWatch Logs
  cloudwatch_logs_retention_in_days = var.log_retention_days
  
  # Environment variables
  environment_variables = {
    SCAN_REGIONS     = join(",", var.scan_regions)
    TARGET_ACCOUNTS  = join(",", var.target_accounts)
    ASSUME_ROLE_NAME = var.scan_role_name
    EXTERNAL_ID      = var.external_id
    OUTPUT_TYPE      = "cloudwatch"
    LOG_LEVEL        = "INFO"
  }
  
  # IAM configuration
  create_role                   = true
  role_name                     = "PerimeterGuardLambdaRole"
  attach_cloudwatch_logs_policy = true
  attach_policy_json            = true
  policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      # Local account scanning permissions
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
    ],
    # Cross-account assume role permission (only if target_accounts configured)
    length(var.target_accounts) > 0 ? [
      {
        Sid    = "AssumeTargetAccountRole"
        Effect = "Allow"
        Action = "sts:AssumeRole"
        Resource = [
          for account_id in var.target_accounts :
          "arn:aws:iam::${account_id}:role/${var.scan_role_name}"
        ]
      }
    ] : [])
  })
  
  tags = merge(var.common_tags, {
    Name      = local.lambda_name
    Purpose   = "AWS Perimeter Guard Scanner"
  })
}

# ============================================
# EventBridge Scheduler (replaces deprecated CloudWatch Events)
# ============================================

# IAM Role for EventBridge Scheduler to invoke Lambda
resource "aws_iam_role" "scheduler_role" {
  name = "PerimeterGuardSchedulerRole"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
  
  tags = merge(var.common_tags, {
    Name    = "PerimeterGuardSchedulerRole"
    Purpose = "AWS Perimeter Guard Scheduler"
  })
}

# IAM Policy for Scheduler to invoke Lambda
resource "aws_iam_role_policy" "scheduler_invoke_lambda" {
  name = "InvokeLambdaPolicy"
  role = aws_iam_role.scheduler_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokeLambda"
        Effect = "Allow"
        Action = "lambda:InvokeFunction"
        Resource = module.lambda_function.lambda_function_arn
      }
    ]
  })
}

# EventBridge Scheduler Schedule
resource "aws_scheduler_schedule" "scanner_schedule" {
  name        = "${local.lambda_name}-schedule"
  description = "Triggers Perimeter Guard scanner on a schedule"
  group_name  = "default"
  
  schedule_expression          = var.scan_schedule
  schedule_expression_timezone = "UTC"
  state                        = "ENABLED"
  
  flexible_time_window {
    mode = "OFF"
  }
  
  target {
    arn      = module.lambda_function.lambda_function_arn
    role_arn = aws_iam_role.scheduler_role.arn
    
    input = jsonencode({
      scan_type = "scheduled"
      timestamp = "EventBridge-scheduled"
    })
    
    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 2
    }
  }
}
