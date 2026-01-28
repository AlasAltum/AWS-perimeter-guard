"""Boto3 AWS Client Adapter - Implementation of AWSClientPort using boto3."""
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.domain.entities import Resource, WebACL
from src.domain.value_objects import ResourceType
from src.ports.outbound import LoggerPort


class Boto3AWSClient:
    """
    Implementation of AWSClientPort using boto3.

    This adapter handles all AWS API interactions for WAF scanning.
    """

    def __init__(
        self,
        logger: LoggerPort,
        session: boto3.Session | None = None,
    ):
        """
        Initialize the AWS client.

        Args:
            logger: Logger for operation logging
            session: Optional boto3 session (uses default if not provided)
        """
        self._logger = logger
        self._session = session or boto3.Session()
        self._client_cache: dict[str, Any] = {}

    def _get_client(self, service: str, region: str) -> Any:
        """Get or create a boto3 client for a service/region combination."""
        cache_key = f"{service}:{region}"
        if cache_key not in self._client_cache:
            self._client_cache[cache_key] = self._session.client(service, region_name=region)
        return self._client_cache[cache_key]

    def get_caller_identity(self) -> dict:
        """Get the current AWS identity."""
        sts = self._get_client("sts", "us-east-1")
        response = sts.get_caller_identity()
        return {
            "account": response["Account"],
            "arn": response["Arn"],
            "user_id": response["UserId"],
        }

    def assume_role(
        self,
        role_arn: str,
        session_name: str,
        external_id: str | None = None,
    ) -> "Boto3AWSClient":
        """
        Assume a role and return a new client with those credentials.

        Args:
            role_arn: ARN of the role to assume
            session_name: Name for the assumed role session
            external_id: Optional external ID for confused deputy prevention

        Returns:
            New Boto3AWSClient with assumed role credentials
        """
        self._logger.info(f"Assuming role: {role_arn}")
        sts = self._get_client("sts", "us-east-1")

        assume_params = {
            "RoleArn": role_arn,
            "RoleSessionName": session_name,
        }
        if external_id:
            assume_params["ExternalId"] = external_id

        response = sts.assume_role(**assume_params)
        credentials = response["Credentials"]
        new_session = boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
        )
        return Boto3AWSClient(logger=self._logger, session=new_session)

    # Resource listing methods

    def list_resources(self, resource_type: ResourceType, region: str) -> list[Resource]:
        """List all resources of a specific type in a region."""
        self._logger.debug(f"Listing {resource_type.display_name} in {region}")

        handlers = {
            ResourceType.ALB: self._list_albs,
            ResourceType.CLOUDFRONT: self._list_cloudfront_distributions,
            ResourceType.API_GATEWAY_REST: self._list_api_gateway_rest_apis,
            ResourceType.API_GATEWAY_HTTP: self._list_api_gateway_http_apis,
            ResourceType.APPSYNC: self._list_appsync_apis,
            ResourceType.COGNITO: self._list_cognito_user_pools,
            ResourceType.APP_RUNNER: self._list_app_runner_services,
            ResourceType.VERIFIED_ACCESS: self._list_verified_access_instances,
        }

        handler = handlers.get(resource_type)
        if handler:
            return handler(region)

        self._logger.warning(f"Unknown resource type: {resource_type}")
        return []

    def _list_albs(self, region: str) -> list[Resource]:
        """List Application Load Balancers."""
        resources = []
        elbv2 = self._get_client("elbv2", region)

        try:
            paginator = elbv2.get_paginator("describe_load_balancers")
            for page in paginator.paginate():
                for lb in page["LoadBalancers"]:
                    if lb["Type"] != "application":
                        continue

                    account_id = lb["LoadBalancerArn"].split(":")[4]
                    is_public = lb.get("Scheme") == "internet-facing"

                    resources.append(Resource(
                        arn=lb["LoadBalancerArn"],
                        resource_type=ResourceType.ALB,
                        region=region,
                        account_id=account_id,
                        name=lb.get("LoadBalancerName"),
                        is_public=is_public,
                    ))
        except ClientError as e:
            self._logger.error(f"Error listing ALBs in {region}", exception=e)

        return resources

    def _list_cloudfront_distributions(self, region: str) -> list[Resource]:
        """List CloudFront distributions (always global, us-east-1)."""
        resources = []
        cloudfront = self._get_client("cloudfront", "us-east-1")

        try:
            paginator = cloudfront.get_paginator("list_distributions")
            for page in paginator.paginate():
                distribution_list = page.get("DistributionList", {})
                items = distribution_list.get("Items", [])
                for dist in items:
                    account_id = dist["ARN"].split(":")[4]

                    # Get full distribution config to check WebACLId
                    dist_id = dist["Id"]
                    web_acl_id = None
                    web_acl = None

                    try:
                        full_dist = cloudfront.get_distribution(Id=dist_id)
                        web_acl_id = full_dist.get("Distribution", {}).get("DistributionConfig", {}).get("WebACLId")

                        if web_acl_id:
                            # Parse WebACL info from ARN
                            # Format: arn:aws:wafv2:us-east-1:account:global/webacl/name/id
                            parts = web_acl_id.split("/")
                            if len(parts) >= 3:
                                web_acl_name = parts[-2]
                                web_acl_uuid = parts[-1]
                                web_acl = WebACL(
                                    arn=web_acl_id,
                                    name=web_acl_name,
                                    id=web_acl_uuid,
                                    scope="CLOUDFRONT",
                                    region="us-east-1",
                                )
                    except ClientError as e:
                        self._logger.debug(f"Could not get distribution {dist_id} details: {e}")

                    resource = Resource(
                        arn=dist["ARN"],
                        resource_type=ResourceType.CLOUDFRONT,
                        region="global",
                        account_id=account_id,
                        name=dist.get("DomainName"),
                        is_public=True,
                        web_acl=web_acl,
                    )
                    resources.append(resource)
        except ClientError as e:
            self._logger.error("Error listing CloudFront distributions", exception=e)

        return resources

    def _list_api_gateway_rest_apis(self, region: str) -> list[Resource]:
        """List API Gateway REST APIs."""
        resources = []
        apigateway = self._get_client("apigateway", region)

        try:
            paginator = apigateway.get_paginator("get_rest_apis")
            for page in paginator.paginate():
                for api in page["items"]:
                    arn = f"arn:aws:apigateway:{region}::/restapis/{api['id']}"

                    resources.append(Resource(
                        arn=arn,
                        resource_type=ResourceType.API_GATEWAY_REST,
                        region=region,
                        account_id=self.get_caller_identity()["account"],
                        name=api.get("name"),
                        is_public=True,
                    ))
        except ClientError as e:
            self._logger.error(f"Error listing API Gateway REST APIs in {region}", exception=e)

        return resources

    def _list_api_gateway_http_apis(self, region: str) -> list[Resource]:
        """List API Gateway HTTP APIs (V2)."""
        resources = []
        apigatewayv2 = self._get_client("apigatewayv2", region)

        try:
            response = apigatewayv2.get_apis()
            for api in response.get("Items", []):
                arn = f"arn:aws:apigateway:{region}::/apis/{api['ApiId']}"

                resources.append(Resource(
                    arn=arn,
                    resource_type=ResourceType.API_GATEWAY_HTTP,
                    region=region,
                    account_id=self.get_caller_identity()["account"],
                    name=api.get("Name"),
                    is_public=True,
                ))
        except ClientError as e:
            self._logger.error(f"Error listing API Gateway HTTP APIs in {region}", exception=e)

        return resources

    def _list_appsync_apis(self, region: str) -> list[Resource]:
        """List AppSync GraphQL APIs."""
        resources = []
        appsync = self._get_client("appsync", region)

        try:
            response = appsync.list_graphql_apis()
            for api in response.get("graphqlApis", []):
                account_id = api["arn"].split(":")[4]

                resources.append(Resource(
                    arn=api["arn"],
                    resource_type=ResourceType.APPSYNC,
                    region=region,
                    account_id=account_id,
                    name=api.get("name"),
                    is_public=True,
                ))
        except ClientError as e:
            self._logger.error(f"Error listing AppSync APIs in {region}", exception=e)

        return resources

    def _list_cognito_user_pools(self, region: str) -> list[Resource]:
        """List Cognito User Pools."""
        resources = []
        cognito = self._get_client("cognito-idp", region)

        try:
            paginator = cognito.get_paginator("list_user_pools")
            for page in paginator.paginate(MaxResults=60):
                for pool in page["UserPools"]:
                    account_id = self.get_caller_identity()["account"]
                    arn = f"arn:aws:cognito-idp:{region}:{account_id}:userpool/{pool['Id']}"

                    resources.append(Resource(
                        arn=arn,
                        resource_type=ResourceType.COGNITO,
                        region=region,
                        account_id=account_id,
                        name=pool.get("Name"),
                        is_public=True,
                    ))
        except ClientError as e:
            self._logger.error(f"Error listing Cognito User Pools in {region}", exception=e)

        return resources

    def _list_app_runner_services(self, region: str) -> list[Resource]:
        """List App Runner Services."""
        resources = []
        apprunner = self._get_client("apprunner", region)

        try:
            next_token = None
            while True:
                if next_token:
                    response = apprunner.list_services(MaxResults=20, NextToken=next_token)
                else:
                    response = apprunner.list_services(MaxResults=20)

                for svc in response.get("ServiceSummaryList", []):
                    account_id = svc["ServiceArn"].split(":")[4]

                    resources.append(Resource(
                        arn=svc["ServiceArn"],
                        resource_type=ResourceType.APP_RUNNER,
                        region=region,
                        account_id=account_id,
                        name=svc.get("ServiceName"),
                        is_public=True,
                    ))

                next_token = response.get("NextToken")
                if not next_token:
                    break

        except ClientError as e:
            self._logger.error(f"Error listing App Runner services in {region}", exception=e)

        return resources

    def _list_verified_access_instances(self, region: str) -> list[Resource]:
        """List Verified Access Instances."""
        resources = []
        ec2 = self._get_client("ec2", region)

        try:
            response = ec2.describe_verified_access_instances()
            for instance in response.get("VerifiedAccessInstances", []):
                instance_id = instance["VerifiedAccessInstanceId"]
                # Build ARN
                account_id = self.get_caller_identity()["account"]
                arn = f"arn:aws:ec2:{region}:{account_id}:verified-access-instance/{instance_id}"

                # Get name from tags
                name = None
                for tag in instance.get("Tags", []):
                    if tag["Key"] == "Name":
                        name = tag["Value"]
                        break

                resources.append(Resource(
                    arn=arn,
                    resource_type=ResourceType.VERIFIED_ACCESS,
                    region=region,
                    account_id=account_id,
                    name=name,
                    is_public=True,
                ))
        except ClientError as e:
            self._logger.error(f"Error listing Verified Access instances in {region}", exception=e)

        return resources

    # WAF methods

    def get_waf_associations_map(self, regions: list[str]) -> dict[str, WebACL]:
        """
        Build a map of resource ARN -> WebACL by listing all WebACLs and their associations.

        This is more efficient and reliable than querying each resource individually.

        For REST APIs, WAF associations are at the stage level (e.g., /restapis/{id}/stages/{stage}),
        but we map them to the API level (e.g., /restapis/{id}) for matching.

        Args:
            regions: List of regions to check for regional WebACLs

        Returns:
            Dictionary mapping resource ARN to WebACL
        """
        associations_map: dict[str, WebACL] = {}

        # Get CloudFront (global) WebACLs - always in us-east-1
        self._logger.debug("Listing CloudFront WebACLs")
        cloudfront_acls = self._list_web_acls_with_resources("CLOUDFRONT", "us-east-1")
        for acl, resource_arns in cloudfront_acls:
            for resource_arn in resource_arns:
                associations_map[resource_arn] = acl

        # Get Regional WebACLs for each region
        for region in regions:
            self._logger.debug(f"Listing Regional WebACLs in {region}")
            regional_acls = self._list_web_acls_with_resources("REGIONAL", region)
            for acl, resource_arns in regional_acls:
                for resource_arn in resource_arns:
                    # For REST API stages, also create API-level mapping
                    # Stage ARN: arn:aws:apigateway:us-east-1::/restapis/1lmtwo0tu8/stages/staging
                    # API ARN: arn:aws:apigateway:us-east-1::/restapis/1lmtwo0tu8
                    if '/restapis/' in resource_arn and '/stages/' in resource_arn:
                        # Extract API-level ARN
                        api_arn = resource_arn.split('/stages/')[0]
                        # Store both stage-level and API-level mappings
                        associations_map[resource_arn] = acl  # Stage-level
                        if api_arn not in associations_map:
                            associations_map[api_arn] = acl  # API-level (first WAF wins)
                    else:
                        associations_map[resource_arn] = acl

        return associations_map

    def _list_web_acls_with_resources(self, scope: str, region: str) -> list[tuple[WebACL, list[str]]]:
        """
        List WebACLs and their associated resources.

        Returns:
            List of tuples (WebACL, List of resource ARNs)
        """
        results = []
        wafv2 = self._get_client("wafv2", region)

        try:
            # List all WebACLs
            response = wafv2.list_web_acls(Scope=scope)
            for acl_summary in response.get("WebACLs", []):
                acl = WebACL(
                    arn=acl_summary["ARN"],
                    name=acl_summary["Name"],
                    id=acl_summary["Id"],
                    scope=scope,
                    region=region,
                    description=acl_summary.get("Description"),
                )

                # Get resources associated with this WebACL
                try:
                    resources_response = wafv2.list_resources_for_web_acl(
                        WebACLArn=acl.arn,
                        ResourceType="APPLICATION_LOAD_BALANCER"
                    )
                    alb_arns = resources_response.get("ResourceArns", [])
                except ClientError:
                    alb_arns = []

                try:
                    resources_response = wafv2.list_resources_for_web_acl(
                        WebACLArn=acl.arn,
                        ResourceType="API_GATEWAY"
                    )
                    api_arns = resources_response.get("ResourceArns", [])
                except ClientError:
                    api_arns = []

                try:
                    resources_response = wafv2.list_resources_for_web_acl(
                        WebACLArn=acl.arn,
                        ResourceType="APPSYNC"
                    )
                    appsync_arns = resources_response.get("ResourceArns", [])
                except ClientError:
                    appsync_arns = []

                try:
                    resources_response = wafv2.list_resources_for_web_acl(
                        WebACLArn=acl.arn,
                        ResourceType="COGNITO_USER_POOL"
                    )
                    cognito_arns = resources_response.get("ResourceArns", [])
                except ClientError:
                    cognito_arns = []

                try:
                    resources_response = wafv2.list_resources_for_web_acl(
                        WebACLArn=acl.arn,
                        ResourceType="APP_RUNNER_SERVICE"
                    )
                    apprunner_arns = resources_response.get("ResourceArns", [])
                except ClientError:
                    apprunner_arns = []

                try:
                    resources_response = wafv2.list_resources_for_web_acl(
                        WebACLArn=acl.arn,
                        ResourceType="VERIFIED_ACCESS_INSTANCE"
                    )
                    verified_access_arns = resources_response.get("ResourceArns", [])
                except ClientError:
                    verified_access_arns = []

                # For CloudFront, we need to query differently
                if scope == "CLOUDFRONT":
                    try:
                        # CloudFront distributions don't use ResourceType parameter
                        resources_response = wafv2.list_resources_for_web_acl(
                            WebACLArn=acl.arn
                        )
                        cloudfront_arns = resources_response.get("ResourceArns", [])
                    except ClientError:
                        cloudfront_arns = []
                else:
                    cloudfront_arns = []

                all_arns = alb_arns + api_arns + appsync_arns + cognito_arns + apprunner_arns + verified_access_arns + cloudfront_arns

                if all_arns:
                    results.append((acl, all_arns))

        except ClientError as e:
            self._logger.error(f"Error listing WebACLs in {scope}/{region}", exception=e)

        return results

    def get_web_acl_for_resource(self, resource_arn: str, resource_type: ResourceType) -> WebACL | None:
        """
        Get the WAF Web ACL associated with a resource.

        DEPRECATED: Use get_waf_associations_map() instead for better performance.
        """
        # Determine scope and region for WAF lookup
        if resource_type.is_cloudfront_scope:
            scope = "CLOUDFRONT"
            waf_region = "us-east-1"
        else:
            scope = "REGIONAL"
            # Extract region from resource ARN
            waf_region = resource_arn.split(":")[3] if ":" in resource_arn else "us-east-1"

        wafv2 = self._get_client("wafv2", waf_region)

        try:
            response = wafv2.get_web_acl_for_resource(ResourceArn=resource_arn)
            web_acl_data = response.get("WebACL")
            if web_acl_data:
                return WebACL(
                    arn=web_acl_data["ARN"],
                    name=web_acl_data["Name"],
                    id=web_acl_data["Id"],
                    scope=scope,
                    region=waf_region,
                    description=web_acl_data.get("Description"),
                )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "WAFNonexistentItemException":
                # No WAF associated - this is expected
                return None
            # Other errors (e.g., WAFInvalidParameterException) also indicate no WAF
            self._logger.debug(f"No WebACL found for {resource_arn}: {error_code}")

        return None

    def list_web_acls(self, scope: str, region: str) -> list[WebACL]:
        """List all Web ACLs in a scope/region."""
        web_acls = []
        waf_region = "us-east-1" if scope == "CLOUDFRONT" else region
        wafv2 = self._get_client("wafv2", waf_region)

        try:
            response = wafv2.list_web_acls(Scope=scope)
            for acl in response.get("WebACLs", []):
                web_acls.append(WebACL(
                    arn=acl["ARN"],
                    name=acl["Name"],
                    id=acl["Id"],
                    scope=scope,
                    region=waf_region,
                    description=acl.get("Description"),
                ))
        except ClientError as e:
            self._logger.error(f"Error listing WebACLs in {scope}/{region}", exception=e)

        return web_acls

    def get_cloudfront_origins_map(self) -> dict[str, list[dict]]:
        """
        Build a map of CloudFront origin domains to CloudFront distributions.

        Returns:
            Dict mapping origin domain → list of dicts with:
            - cloudfront_arn: ARN of the CloudFront distribution
            - cloudfront_id: Distribution ID
            - cloudfront_domain: Distribution domain name
            - web_acl: WebACL object if distribution has WAF

        Example:
            {
                "o5yl95v1g1.execute-api.us-east-1.amazonaws.com": [
                    {
                        "cloudfront_arn": "arn:aws:cloudfront::...:distribution/E3T3BYVBS5ILLA",
                        "cloudfront_id": "E3T3BYVBS5ILLA",
                        "cloudfront_domain": "dcsy7pe26thzz.cloudfront.net",
                        "web_acl": WebACL(...)
                    }
                ]
            }
        """
        origins_map: dict[str, list[dict]] = {}
        account_id = self.get_caller_identity()["account"]

        # Get all CloudFront distributions
        cloudfront = self._get_client('cloudfront', 'us-east-1')
        paginator = cloudfront.get_paginator('list_distributions')

        try:
            for page in paginator.paginate():
                if 'Items' not in page.get('DistributionList', {}):
                    continue

                for dist_summary in page['DistributionList']['Items']:
                    dist_id = dist_summary['Id']

                    try:
                        # Get full distribution config (includes origins and WebACLId)
                        full_dist = cloudfront.get_distribution(Id=dist_id)
                        config = full_dist['Distribution']['DistributionConfig']

                        # Parse WebACL if present
                        web_acl = None
                        web_acl_id = config.get('WebACLId', '')
                        if web_acl_id:
                            # Parse ARN: arn:aws:wafv2:region:account:global/webacl/name/id
                            web_acl = self._parse_waf_arn(web_acl_id)

                        # Extract all origins
                        origins = config.get('Origins', {}).get('Items', [])
                        for origin in origins:
                            domain = origin['DomainName']

                            # Skip S3 origins (we only care about API Gateway and ALB origins)
                            if '.s3.' in domain or '.s3-' in domain:
                                continue

                            if domain not in origins_map:
                                origins_map[domain] = []

                            origins_map[domain].append({
                                'cloudfront_arn': f"arn:aws:cloudfront::{account_id}:distribution/{dist_id}",
                                'cloudfront_id': dist_id,
                                'cloudfront_domain': dist_summary['DomainName'],
                                'web_acl': web_acl
                            })
                    except ClientError as e:
                        self._logger.debug(f"Error getting distribution {dist_id}: {e}")
                        continue
        except ClientError as e:
            self._logger.error("Error listing CloudFront distributions for origins map", exception=e)

        self._logger.info(f"Built CloudFront origins map with {len(origins_map)} unique origins")
        return origins_map

    def match_resource_to_origin(self, resource: Resource) -> str | None:
        """
        Extract the origin domain from a resource.

        Args:
            resource: Resource to extract origin domain from

        Returns:
            Origin domain string if matchable, None otherwise

        Examples:
            HTTP API: "o5yl95v1g1.execute-api.us-east-1.amazonaws.com"
            REST API: "1jnx7rksc5.execute-api.us-east-1.amazonaws.com"
            ALB: "k8s-name-hash.elb.us-east-1.amazonaws.com"
        """
        if resource.resource_type == ResourceType.API_GATEWAY_HTTP:
            # Extract API ID from ARN: arn:aws:apigateway:us-east-1::/apis/o5yl95v1g1
            api_id = resource.arn.split('/apis/')[-1]
            return f"{api_id}.execute-api.{resource.region}.amazonaws.com"

        elif resource.resource_type == ResourceType.API_GATEWAY_REST:
            # Extract API ID from ARN: arn:aws:apigateway:us-east-1::/restapis/1jnx7rksc5
            api_id = resource.arn.split('/restapis/')[-1]
            return f"{api_id}.execute-api.{resource.region}.amazonaws.com"

        elif resource.resource_type == ResourceType.ALB:
            # Get ALB DNS name from AWS
            return self._get_alb_dns_name(resource.arn, resource.region)

        return None

    def _get_alb_dns_name(self, alb_arn: str, region: str) -> str | None:
        """
        Get ALB DNS name from its ARN.

        Args:
            alb_arn: ARN of the ALB
            region: AWS region

        Returns:
            DNS name like "k8s-name-hash.elb.us-east-1.amazonaws.com" or None
        """
        try:
            elbv2 = self._get_client('elbv2', region)
            response = elbv2.describe_load_balancers(LoadBalancerArns=[alb_arn])
            if response['LoadBalancers']:
                return response['LoadBalancers'][0]['DNSName']
        except ClientError as e:
            self._logger.debug(f"Could not get ALB DNS name for {alb_arn}: {e}")
        return None

    def _parse_waf_arn(self, waf_arn: str) -> WebACL | None:
        """
        Parse WebACL information from a WAF ARN.

        Args:
            waf_arn: WAF ARN in format: arn:aws:wafv2:region:account:scope/webacl/name/id

        Returns:
            WebACL object or None if parsing fails

        Example ARN format:
            arn:aws:wafv2:region:account:scope/webacl/name/id
        """
        try:
            parts = waf_arn.split("/")
            if len(parts) >= 3:
                web_acl_name = parts[-2]
                web_acl_uuid = parts[-1]

                # Extract scope and region from ARN prefix
                arn_prefix = waf_arn.split(":")[5]  # Gets "global/webacl" or "regional/webacl"
                scope = "CLOUDFRONT" if arn_prefix.startswith("global") else "REGIONAL"
                region = waf_arn.split(":")[3]

                return WebACL(
                    arn=waf_arn,
                    name=web_acl_name,
                    id=web_acl_uuid,
                    scope=scope,
                    region=region,
                )
        except (IndexError, ValueError) as e:
            self._logger.debug(f"Could not parse WAF ARN {waf_arn}: {e}")

        return None
