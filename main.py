from prefect import flow, task, get_run_logger
import boto3
from datetime import datetime, timedelta

from davinci.services.auth import get_secret
import warnings
import pandas as pd
warnings.filterwarnings("ignore")

@task
def get_task_definition_families(cluster_name):
    """
    Get all the TaskDefinitionFamilies associated with a given ECS cluster.

    Args:
    - cluster_name: Name of the ECS cluster

    Returns:
    - List of TaskDefinitionFamilies
    """
    boto3_login = {
        "verify": False,
        "service_name": 'ecs',
        "region_name": 'us-east-1',
        "aws_access_key_id": get_secret("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": get_secret("AWS_SECRET_ACCESS_KEY")
    }
    ecs = boto3.client(**boto3_login)

    task_definition_families = set()
    next_token = None

    num_api_calls = 0

    while True:
        # Retrieve all task definitions in the specified cluster
        if next_token == None:
            response = ecs.list_task_definitions(status='ACTIVE', sort='DESC', maxResults=100)
        else:
            response = ecs.list_task_definitions(status='ACTIVE', sort='DESC', maxResults=100, nextToken=next_token)
        # print(response)
        num_api_calls += 1

        task_definitions = response['taskDefinitionArns']

        # Extract the family name from each task definition ARN
        for task_definition_arn in task_definitions:
            family_name = task_definition_arn.split('/')[-1].split(':')[0]
            task_definition_families.add(family_name)

        next_token = response.get('nextToken')
        if next_token == None:
            break

    print("number of API calls", num_api_calls)

    return list(task_definition_families)

@task
def fetch_ecs_metrics(cloudwatch, cluster_name, task_definition_family):
    # Define the time period for the metrics
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=7)  # Last 7 days
    print(start_time, end_time)

    # Helper to fetch metrics
    def get_metric(metric_name, stat):
        response = cloudwatch.get_metric_data(
            MetricDataQueries=[
                {
                    'Id': 'm1',
                    'MetricStat': {
                        'Metric': {
                            'Namespace': 'ECS/ContainerInsights',  # 'AWS/ECS',
                            'MetricName': metric_name,
                            'Dimensions': [
                                {'Name': 'ClusterName', 'Value': cluster_name},
                                {'Name': 'TaskDefinitionFamily', 'Value': task_definition_family}
                            ]
                        },
                        'Period': 7 * 86400,  # 7 days
                        'Stat': stat,
                    },
                    'ReturnData': True,
                },
            ],
            StartTime=start_time,
            EndTime=end_time
        )
        # print(response)
        return response['MetricDataResults'][0]['Values']

    # Fetch CPU and memory metrics
    cpu_utilization = get_metric('CpuUtilized', 'Average')
    cpu_max = get_metric('CpuUtilized', 'Maximum')
    cpu_reserved = get_metric('CpuReserved', 'Average')
    memory_utilization = get_metric('MemoryUtilized', 'Average')
    memory_max = get_metric('MemoryUtilized', 'Maximum')
    memory_reserved = get_metric('MemoryReserved', 'Average')

    return cpu_utilization, cpu_max, cpu_reserved, memory_utilization, memory_max, memory_reserved


@flow(name='prefect-container-utilisation-task-flow', retries=3, retry_delay_seconds=30)
def main(config=None):
    # config = config if config else {}
    # logger = get_run_logger()
    # logger.info('Entering...')
    # logger.info(config.get('alpha', 'No Parameter Passed!'))
    # res = basic()

    # Create a CloudWatch client
    boto3_login = {
        "verify": False,
        "service_name": 'cloudwatch',
        "region_name": 'us-east-1',
        "aws_access_key_id": get_secret("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": get_secret("AWS_SECRET_ACCESS_KEY")
    }
    cloudwatch = boto3.client(**boto3_login)

    # Replace 'YourClusterName' and 'YourTaskDefinitionFamily' with your ECS cluster and task definition family
    cluster_name = 'ECSClusterDev'
    # task_definition_family = 'dash_bb_pick_path-pickpath-optimizer-dev'
    task_definition_families = get_task_definition_families(cluster_name)

    rows_list = []

    for task_definition_family in task_definition_families:
        cpu_util, cpu_max, cpu_reserved, mem_util, mem_max, mem_reserved = fetch_ecs_metrics(cloudwatch, cluster_name,
                                                                                             task_definition_family)
        print(task_definition_family)
        print("CPU Utilization:", cpu_util)
        print("CPU Max:", cpu_max)
        print("CPU Reserved:", cpu_reserved)
        print("Memory Utilization:", mem_util)
        print("Memory Max:", mem_max)
        print("Memory Reserved:", mem_reserved)

        if (cpu_util and cpu_max and cpu_reserved and
                mem_util and mem_max and mem_reserved):
            cpu_savings = None
            mem_savings = None
            if (cpu_util[0] / cpu_reserved[0]) < 0.5:
                cpu_savings = cpu_reserved[0] * (1 - (cpu_util[0] / cpu_reserved[0]) / 0.5)
            elif (cpu_util[0] / cpu_reserved[0]) > 0.8:
                cpu_savings = cpu_reserved[0] * (1 - (cpu_util[0] / cpu_reserved[0]) / 0.8)
            if (mem_util[0] / mem_reserved[0]) < 0.5:
                mem_savings = mem_reserved[0] * (1 - (mem_util[0] / mem_reserved[0]) / 0.5)
            elif (mem_util[0] / mem_reserved[0]) > 0.8:
                mem_savings = mem_reserved[0] * (1 - (mem_util[0] / mem_reserved[0]) / 0.8)

            if ((cpu_util[0] / cpu_reserved[0]) < 0.5) or ((cpu_util[0] / cpu_reserved[0]) > 0.8) \
                    or ((mem_util[0] / mem_reserved[0]) < 0.5) or ((mem_util[0] / mem_reserved[0]) > 0.8):
                rows_list.append({'Task Name': task_definition_family, 'Average CPU': cpu_util[0],
                                  'Max CPU': cpu_max[0], 'CPU Reserved': cpu_reserved[0],
                                  'Average Memory': mem_util[0], 'Max Memory': mem_max[0],
                                  'Memory Reserved': mem_reserved[0],
                                  'CPU Savings': cpu_savings, 'Memory Savings': mem_savings})

    df = pd.DataFrame(rows_list)
    print(df)

    # return res
    return

if __name__ == "__main__":
    main()