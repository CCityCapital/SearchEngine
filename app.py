from aws_cdk import (
    Environment,
    Fn,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ecr_assets as ecr_assets,
    aws_secretsmanager as secretsmanager,
    App,
    Stack,
)
from constructs import Construct

import os
from pathlib import Path

CURR_DIR = Path(os.path.dirname(__file__))


class CorpusStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc_id: str,
        secret_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.construct_id = construct_id

        vpc = ec2.Vpc.from_lookup(self, f"vpc-{construct_id}", vpc_id=vpc_id)

        self.qa_cluster = ecs.Cluster(
            self,
            f"{construct_id}-qa-cluster",
            vpc=vpc,
            cluster_name=f"{construct_id}-qa-cluster",
        )

        self.open_api_secret = secretsmanager.Secret.from_secret_complete_arn(
            self,
            f"{construct_id}-open-api-secret",
            secret_complete_arn=secret_arn,
        )

        vector_db = self.create_vector_db()

        qa_api = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            f"{construct_id}-qa-api",
            service_name=f"{construct_id}-qa-api",
            cluster=self.qa_cluster,
            desired_count=1,
            cpu=1024,
            memory_limit_mib=2048,
            assign_public_ip=True,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset(
                    directory=(CURR_DIR).as_posix(),
                    file="app.dockerfile",
                    platform=ecr_assets.Platform.LINUX_AMD64,
                ),
                container_port=8000,
                environment={
                    "VECTOR_DB_URL": Fn.join(
                        "",
                        [
                            "http://",
                            vector_db.load_balancer.load_balancer_dns_name,
                            ":8080",
                        ],
                    )
                },
                secrets={
                    "OPENAI_API_KEY": ecs.Secret.from_secrets_manager(
                        self.open_api_secret
                    )
                },
            ),
            task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        # allow task execution role to retrieve secrets
        self.open_api_secret.grant_read(qa_api.task_definition.execution_role)

        # api depends on vector db to be up and running
        qa_api.node.add_dependency(vector_db)

    def create_vector_db(
        self,
    ) -> ecs_patterns.ApplicationLoadBalancedFargateService:
        backend_subnets = ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)

        vector_db = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            f"{self.construct_id}-qa-weaviate-service",
            service_name=f"{self.construct_id}-qa-weaviate-service",
            cluster=self.qa_cluster,
            desired_count=1,
            cpu=1024,
            memory_limit_mib=2048,
            assign_public_ip=True,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_registry(
                    "semitechnologies/weaviate:1.19.9"
                ),
                container_port=8080,
                environment={
                    "QUERY_DEFAULTS_LIMIT": "20",
                    "AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED": "true",
                    "PERSISTENCE_DATA_PATH": "./test-data",
                    "ENABLE_MODULES": "text2vec-openai,generative-openai",
                    "CLUSTER_HOSTNAME": "node1",
                },
            ),
            task_subnets=backend_subnets,
            listener_port=8080,
        )

        vector_db.target_group.configure_health_check(
            path="/v1/.well-known/ready", healthy_http_codes="200-299"
        )

        return vector_db


app = App()

CorpusStack(
    app,
    "corpus-query-dev",
    vpc_id="vpc-04d3285b792f77374",
    env=Environment(region="us-east-2", account="631140025723"),
    secret_arn="arn:aws:secretsmanager:us-east-2:631140025723:secret:dev/open-api-secret-aSQKKG",
)

app.synth()
