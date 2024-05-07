FROM 823367020558.dkr.ecr.us-east-1.amazonaws.com/kencologistics/codebase@sha256:51e1bdfa04d4c3f777b439c66d154271b5c8042963bfd888875fd33cc67ec4ef

## DEVELOPER TODO: MODFIY THE BELOW LINE TO MATCH THE NAME OF THE REPO.
## WORKDIR /home/ubunut/{repo_name}
WORKDIR /home/ubuntu/prefect_ecs

## Pip install any new dependencies
## Note that this means you might potentially overwrite libraries for codebase
## Use and test at your own discretion.
COPY ./requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
COPY ./ ./

## Setup prod indicators
ARG PROD_FLAG
ENV DAVINCI_PROD=$PROD_FLAG

# Entrypoint
CMD ["/bin/bash"]