"""Resource type enumeration for AWS resources supporting WAF."""
from enum import Enum


class ResourceType(str, Enum):
    """AWS resource types that support WAF association."""

    ALB = "APPLICATION_LOAD_BALANCER"
    CLOUDFRONT = "CLOUDFRONT_DISTRIBUTION"
    API_GATEWAY_REST = "API_GATEWAY_REST_API"
    API_GATEWAY_HTTP = "API_GATEWAY_HTTP_API"
    APPSYNC = "APPSYNC_GRAPHQL_API"
    COGNITO = "COGNITO_USER_POOL"
    APP_RUNNER = "APP_RUNNER_SERVICE"
    VERIFIED_ACCESS = "VERIFIED_ACCESS_INSTANCE"

    @property
    def waf_resource_type(self) -> str:
        """Return the WAFv2 API resource type string."""
        return self.value

    @property
    def is_cloudfront_scope(self) -> bool:
        """Check if resource uses CLOUDFRONT scope in WAFv2."""
        return self == ResourceType.CLOUDFRONT

    @property
    def aws_service(self) -> str:
        """Return the AWS service name for this resource."""
        mapping = {
            ResourceType.ALB: "elasticloadbalancing",
            ResourceType.CLOUDFRONT: "cloudfront",
            ResourceType.API_GATEWAY_REST: "apigateway",
            ResourceType.API_GATEWAY_HTTP: "apigateway",
            ResourceType.APPSYNC: "appsync",
            ResourceType.COGNITO: "cognito-idp",
            ResourceType.APP_RUNNER: "apprunner",
            ResourceType.VERIFIED_ACCESS: "ec2",
        }
        return mapping[self]

    @property
    def display_name(self) -> str:
        """Human-readable name for the resource type."""
        mapping = {
            ResourceType.ALB: "Application Load Balancer",
            ResourceType.CLOUDFRONT: "CloudFront Distribution",
            ResourceType.API_GATEWAY_REST: "API Gateway REST API",
            ResourceType.API_GATEWAY_HTTP: "API Gateway HTTP API",
            ResourceType.APPSYNC: "AppSync GraphQL API",
            ResourceType.COGNITO: "Cognito User Pool",
            ResourceType.APP_RUNNER: "App Runner Service",
            ResourceType.VERIFIED_ACCESS: "Verified Access Instance",
        }
        return mapping[self]
