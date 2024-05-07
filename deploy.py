from prefect.deployments import Deployment
from prefect.server.schemas.schedules import CronSchedule
from davinci.utils.global_config import ENV
from davinci.services.auth import get_secret

from main import main
import os
import subprocess


def build_deployment():
    task_family = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], universal_newlines=True).strip().split('/')[-1]

    ### DO NOT ADJUST. This tells Prefect what Docker contain to reference ###
    image = "".join([
        get_secret("AWS_ACCOUNT_ID"),
        '.dkr.ecr.us-east-1.amazonaws.com/kencologistics/',
        f'{task_family}:{ENV}',
    ])
    ##########################################################################

    deployment = Deployment.build_from_flow(
        flow=main,
        name=f"test-ecs-deployment-{ENV}", # TODO, name this whatever you wish. Keep the suffix ENV for tracking purposes.
        work_pool_name=f"ecs-wp-{ENV}",
        infra_overrides={
            "image": image,
            # https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ecs-taskdefinition.html#cfn-ecs-taskdefinition-cpu
            "cpu": 256, # TODO modify the cpu value accordingly for your job. Be as conservative as possible and do not exceed 1024
            "memory": 512, # TODO modify the memory amount. This is contrained by whatever cpu option you select. Review the link above.
            "launch_type": "FARGATE_SPOT", # TODO select an option out of ['FARGATE', 'FARGATE_SPOT', 'EC2']
            "family": f'{task_family}-{ENV}',
            "cloudwatch_logs_options": {
                "mode": "non-blocking",
                "awslogs-group": f"prefect-jobs-{ENV}",
                "awslogs-region": "us-east-1",
                "max-buffer-size": "5m",
                "awslogs-create-group": "true",
                "awslogs-stream-prefix": task_family
            }
        },
        # TODO adjust the below as desired.
        parameters={}, # These feed into your flow.
        is_schedule_active=False,
        schedule=(CronSchedule(cron="20 * * * *", timezone="America/New_York")),
        tags=['ecs', task_family, ENV],
    )
    deployment.apply()


if __name__ == "__main__":
    build_deployment()