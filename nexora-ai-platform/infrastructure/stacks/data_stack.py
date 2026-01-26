"""
Data Stack for Nexora AI Platform.

This stack creates all data storage resources including:
- DynamoDB tables for application data
- S3 buckets for content storage
- Amazon OpenSearch for vector storage
- ElastiCache Redis for caching
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_opensearchserverless as opensearch,
    aws_elasticache as elasticache,
    aws_ec2 as ec2,
    aws_iam as iam,
)
from constructs import Construct


class DataStack(Stack):
    """Stack for data storage resources."""

    def __init__(self, scope: Construct, construct_id: str, stage: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.stage = stage

        # Create DynamoDB tables
        self._create_dynamodb_tables()

        # Create S3 buckets
        self._create_s3_buckets()

        # Create OpenSearch Serverless collection
        self._create_opensearch_collection()

        # Create VPC for ElastiCache (if needed)
        self._create_vpc()

        # Create ElastiCache Redis cluster
        self._create_redis_cluster()

    def _create_dynamodb_tables(self) -> None:
        """Create DynamoDB tables for the application."""
        
        # Users table
        self.users_table = dynamodb.Table(
            self,
            "UsersTable",
            table_name=f"nexora-users-{self.stage}",
            partition_key=dynamodb.Attribute(
                name="user_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY if self.stage == "dev" else RemovalPolicy.RETAIN,
            point_in_time_recovery=True,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        )

        # Add GSI for tenant-based queries
        self.users_table.add_global_secondary_index(
            index_name="tenant-index",
            partition_key=dynamodb.Attribute(
                name="tenant_id", type=dynamodb.AttributeType.STRING
            ),
        )

        # Tenants table
        self.tenants_table = dynamodb.Table(
            self,
            "TenantsTable",
            table_name=f"nexora-tenants-{self.stage}",
            partition_key=dynamodb.Attribute(
                name="tenant_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY if self.stage == "dev" else RemovalPolicy.RETAIN,
            point_in_time_recovery=True,
        )

        # Content Requests table
        self.content_requests_table = dynamodb.Table(
            self,
            "ContentRequestsTable",
            table_name=f"nexora-content-requests-{self.stage}",
            partition_key=dynamodb.Attribute(
                name="tenant_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="request_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY if self.stage == "dev" else RemovalPolicy.RETAIN,
            point_in_time_recovery=True,
            time_to_live_attribute="ttl",
        )

        # Add GSI for user-based queries
        self.content_requests_table.add_global_secondary_index(
            index_name="user-index",
            partition_key=dynamodb.Attribute(
                name="user_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at", type=dynamodb.AttributeType.STRING
            ),
        )

        # Generated Content table
        self.generated_content_table = dynamodb.Table(
            self,
            "GeneratedContentTable",
            table_name=f"nexora-generated-content-{self.stage}",
            partition_key=dynamodb.Attribute(
                name="tenant_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="content_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY if self.stage == "dev" else RemovalPolicy.RETAIN,
            point_in_time_recovery=True,
            time_to_live_attribute="ttl",
        )

        # Add GSI for request-based queries
        self.generated_content_table.add_global_secondary_index(
            index_name="request-index",
            partition_key=dynamodb.Attribute(
                name="request_id", type=dynamodb.AttributeType.STRING
            ),
        )

        # Workflow Executions table
        self.workflow_executions_table = dynamodb.Table(
            self,
            "WorkflowExecutionsTable",
            table_name=f"nexora-workflow-executions-{self.stage}",
            partition_key=dynamodb.Attribute(
                name="tenant_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="execution_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY if self.stage == "dev" else RemovalPolicy.RETAIN,
            point_in_time_recovery=True,
        )

        # Publications table
        self.publications_table = dynamodb.Table(
            self,
            "PublicationsTable",
            table_name=f"nexora-publications-{self.stage}",
            partition_key=dynamodb.Attribute(
                name="tenant_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="publication_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY if self.stage == "dev" else RemovalPolicy.RETAIN,
            point_in_time_recovery=True,
        )

    def _create_s3_buckets(self) -> None:
        """Create S3 buckets for content storage."""
        
        # Main content bucket
        self.content_bucket = s3.Bucket(
            self,
            "ContentBucket",
            bucket_name=f"nexora-content-{self.stage}-{self.account}",
            removal_policy=RemovalPolicy.DESTROY if self.stage == "dev" else RemovalPolicy.RETAIN,
            auto_delete_objects=self.stage == "dev",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldVersions",
                    enabled=True,
                    noncurrent_version_expiration=Duration.days(30),
                ),
                s3.LifecycleRule(
                    id="TransitionToIA",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30),
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90),
                        ),
                    ],
                ),
            ],
        )

        # Analytics bucket for logs and metrics
        self.analytics_bucket = s3.Bucket(
            self,
            "AnalyticsBucket",
            bucket_name=f"nexora-analytics-{self.stage}-{self.account}",
            removal_policy=RemovalPolicy.DESTROY if self.stage == "dev" else RemovalPolicy.RETAIN,
            auto_delete_objects=self.stage == "dev",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

    def _create_opensearch_collection(self) -> None:
        """Create OpenSearch Serverless collection for vector storage."""
        
        # Create security policy for the collection
        security_policy = opensearch.CfnSecurityPolicy(
            self,
            "OpenSearchSecurityPolicy",
            name=f"nexora-security-policy-{self.stage}",
            type="encryption",
            policy=f"""{{
                "Rules": [
                    {{
                        "ResourceType": "collection",
                        "Resource": ["collection/nexora-vectors-{self.stage}"]
                    }}
                ],
                "AWSOwnedKey": true
            }}""",
        )

        # Create network policy
        network_policy = opensearch.CfnSecurityPolicy(
            self,
            "OpenSearchNetworkPolicy",
            name=f"nexora-network-policy-{self.stage}",
            type="network",
            policy=f"""[{{
                "Rules": [
                    {{
                        "ResourceType": "collection",
                        "Resource": ["collection/nexora-vectors-{self.stage}"]
                    }},
                    {{
                        "ResourceType": "dashboard",
                        "Resource": ["collection/nexora-vectors-{self.stage}"]
                    }}
                ],
                "AllowFromPublic": true
            }}]""",
        )

        # Create the collection
        self.opensearch_collection = opensearch.CfnCollection(
            self,
            "OpenSearchCollection",
            name=f"nexora-vectors-{self.stage}",
            type="VECTORSEARCH",
            description="Vector storage for Nexora AI RAG pipeline",
        )

        # Add dependencies
        self.opensearch_collection.add_dependency(security_policy)
        self.opensearch_collection.add_dependency(network_policy)

    def _create_vpc(self) -> None:
        """Create VPC for ElastiCache."""
        
        self.vpc = ec2.Vpc(
            self,
            "NexoraVPC",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
            ],
        )

    def _create_redis_cluster(self) -> None:
        """Create ElastiCache Redis cluster for caching."""
        
        # Create security group for Redis
        redis_security_group = ec2.SecurityGroup(
            self,
            "RedisSecurityGroup",
            vpc=self.vpc,
            description="Security group for Redis cluster",
            allow_all_outbound=False,
        )

        # Allow inbound Redis traffic from VPC
        redis_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(6379),
            description="Redis access from VPC",
        )

        # Create subnet group
        subnet_group = elasticache.CfnSubnetGroup(
            self,
            "RedisSubnetGroup",
            description="Subnet group for Redis cluster",
            subnet_ids=[subnet.subnet_id for subnet in self.vpc.private_subnets],
        )

        # Create Redis cluster
        self.redis_cluster = elasticache.CfnCacheCluster(
            self,
            "RedisCluster",
            cache_node_type="cache.t3.micro" if self.stage == "dev" else "cache.r6g.large",
            engine="redis",
            num_cache_nodes=1,
            cache_subnet_group_name=subnet_group.ref,
            vpc_security_group_ids=[redis_security_group.security_group_id],
            port=6379,
        )