from prefect import flow, task, get_run_logger
import boto3
from datetime import datetime, timedelta

from davinci.services.auth import get_secret
from davinci.services.outlook import DavinciEmail
import warnings
import pandas as pd
warnings.filterwarnings("ignore")

@task
def get_task_definition_families():
    """
    Get all the TaskDefinitionFamilies.

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
def fetch_ecs_metrics_all(cloudwatch, task_definition_families, rows_list):
    # Define the time period for the metrics
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=7)  # Last 7 days
    print(start_time, end_time)

    for task_definition_family in task_definition_families:
        for cluster_name in ["ECSClusterProd", "ECSClusterDev"]:
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

            cpu_util, cpu_max, cpu_reserved, mem_util, mem_max, mem_reserved = cpu_utilization, cpu_max, cpu_reserved, memory_utilization, memory_max, memory_reserved

            print(task_definition_family)
            print(f"CPU Utilization: {cpu_util}; CPU Max: {cpu_max}; "
                  f"CPU Reserved: {cpu_reserved}; Memory Utilization: {mem_util}"
                  f"Memory Max: {mem_max}; Memory Reserved: {mem_reserved}")

            if (cpu_util and cpu_max and cpu_reserved and
                    mem_util and mem_max and mem_reserved):
                cpu_savings = 0
                mem_savings = 0
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
                    rows_list.append({'Task Name': task_definition_family, 'Average CPU': round(cpu_util[0]),
                                      'Max CPU': round(cpu_max[0]), 'CPU Reserved': round(cpu_reserved[0]),
                                      'Average Memory': round(mem_util[0]), 'Max Memory': round(mem_max[0]),
                                      'Memory Reserved': round(mem_reserved[0]),
                                      'CPU Savings': round(cpu_savings), 'Memory Savings': round(mem_savings),
                                      'CPU + Memory Savings': round(cpu_savings + mem_savings)})

    return rows_list

@flow(name='prefect-container-utilisation-task-flow', retries=3, retry_delay_seconds=30, log_prints=True)
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

    task_definition_families = get_task_definition_families()
    print("Number of task_definition_families:", len(task_definition_families))

    rows_list = []
    rows_list = fetch_ecs_metrics_all(cloudwatch, task_definition_families, rows_list)

    df = pd.DataFrame(rows_list)
    df = df.sort_values('CPU + Memory Savings', ascending=False)
    print(df)

    email = DavinciEmail(f"Tasks over-utilizing or under-utilizing CPU and Memory resources",
                         "<h3>Please find data attached for tasks falling above "
                         "or below 50%-80% threshold for CPU and Memory resource-utilization.</h3>", False)
    email.embed_df_as_html_table(df, color='blue_light', font_size=14, text_align='center')
    recipients = get_secret('DEV_TEAM')
    email.send(list(set(recipients)))  # unique recipients
    print('Email Sent.')

    # return res
    return

if __name__ == "__main__":
    main()