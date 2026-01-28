"""AWS Client Port - Interface for AWS operations."""
from typing import Protocol

from src.domain.entities import Resource, WebACL
from src.domain.value_objects import ResourceType


class AWSClientPort(Protocol):
    """
    Port interface for AWS operations.

    This protocol defines all AWS interactions needed for WAF scanning.
    Implementations should use boto3 or mocks for testing.
    """

    def list_resources(self, resource_type: ResourceType, region: str) -> list[Resource]:
        """
        List all resources of a specific type in a region.

        Args:
            resource_type: Type of resource to list
            region: AWS region

        Returns:
            List of Resource objects (without WAF information yet)
        """
        ...

    def get_waf_associations_map(self, regions: list[str]) -> dict[str, WebACL]:
        """
        Build a map of resource ARN -> WebACL by listing all WebACLs and their associations.

        This is more efficient than querying each resource individually.

        Args:
            regions: List of regions to check for regional WebACLs

        Returns:
            Dictionary mapping resource ARN to WebACL
        """
        ...

    def get_web_acl_for_resource(self, resource_arn: str, resource_type: ResourceType) -> WebACL | None:
        """
        Get the WAF Web ACL associated with a resource.

        DEPRECATED: Use get_waf_associations_map() instead for better performance.

        Args:
            resource_arn: ARN of the resource
            resource_type: Type of the resource (determines WAF scope)

        Returns:
            WebACL if associated, None otherwise
        """
        ...

    def list_web_acls(self, scope: str, region: str) -> list[WebACL]:
        """
        List all Web ACLs in a scope/region.

        Args:
            scope: "REGIONAL" or "CLOUDFRONT"
            region: AWS region (use "us-east-1" for CLOUDFRONT scope)

        Returns:
            List of WebACL objects
        """
        ...

    def get_caller_identity(self) -> dict:
        """
        Get the current AWS identity.

        Returns:
            Dict with account, arn, user_id
        """
        ...

    def assume_role(self, role_arn: str, session_name: str) -> "AWSClientPort":
        """
        Assume a role and return a new client with those credentials.

        Args:
            role_arn: ARN of the role to assume
            session_name: Name for the assumed role session

        Returns:
            New AWSClientPort instance with assumed credentials
        """
        ...
