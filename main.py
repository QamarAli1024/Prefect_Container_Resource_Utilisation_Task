from prefect import flow, task, get_run_logger

@task
def basic():
    return 5


@flow(name='ecs-single-flow', retries=3, retry_delay_seconds=30)
def main(config=None):
    config = config if config else {}
    logger = get_run_logger()
    logger.info('Entering...')
    logger.info(config.get('alpha', 'No Parameter Passed!'))
    res = basic()
    return res