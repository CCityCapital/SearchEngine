from typing import Tuple
from aws_cdk import (
    Environment,
    Fn,
    aws_autoscaling as autoscaling,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ecr as ecr,
    aws_ecr_assets as ecr_assets,
    aws_events as events,
    App,
    CfnOutput,
    Stack,
)
from constructs import Construct

import os
from pathlib import Path

CURR_DIR = Path(os.path.dirname(__file__))


class CorpusStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, vpc_id: str, **kwargs
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

        vector_db, embedding_service = self.create_vector_db()

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
            ),
            task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

    def create_vector_db(
        self,
    ) -> Tuple[
        ecs_patterns.ApplicationLoadBalancedFargateService,
        ecs_patterns.ApplicationLoadBalancedFargateService,
    ]:
        backend_subnets = ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)

        embedding_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            f"{self.construct_id}-qa-embedding-service",
            service_name=f"{self.construct_id}-qa-embedding-service",
            cluster=self.qa_cluster,
            desired_count=1,
            cpu=1024,
            memory_limit_mib=2048,
            assign_public_ip=True,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_registry(
                    "semitechnologies/transformers-inference:sentence-transformers-multi-qa-MiniLM-L6-cos-v1"
                ),
                container_port=8080,
            ),
            task_subnets=backend_subnets,
            listener_port=8080,
        )

        embedding_service.target_group.configure_health_check(
            path="/.well-known/live", healthy_http_codes="200-299"
        )

        embedding_service.load_balancer.health_check = None
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
                    "DEFAULT_VECTORIZER_MODULE": "text2vec-transformers",
                    "ENABLE_MODULES": "text2vec-transformers",
                    "TRANSFORMERS_INFERENCE_API": Fn.join(
                        "",
                        [
                            "http://",
                            embedding_service.load_balancer.load_balancer_dns_name,
                            ":8080",
                        ],
                    ),
                    "CLUSTER_HOSTNAME": "node1",
                },
            ),
            task_subnets=backend_subnets,
            listener_port=8080,
        )

        vector_db.target_group.configure_health_check(
            path="/v1/.well-known/ready", healthy_http_codes="200-299"
        )

        vector_db.node.add_dependency(embedding_service)
        return vector_db, embedding_service


app = App()

CorpusStack(
    app,
    "corpus-query-dev",
    vpc_id="vpc-04d3285b792f77374",
    env=Environment(region="us-east-2", account="631140025723"),
)

app.synth()
