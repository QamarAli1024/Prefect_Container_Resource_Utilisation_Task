from prefect.deployments import run_deployment
from davinci.utils.global_config import ENV

if __name__ == '__main__':
    for i in 'abc':
        config = {'alpha': i}
        run_deployment(
            f'ecs-single-flow/test-ecs-deployment-{ENV}',
            flow_run_name=f'ecs-single-flow-{i}',
            timeout=0,
            parameters={'config': i}
        )