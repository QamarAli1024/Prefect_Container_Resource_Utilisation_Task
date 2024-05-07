# Prefect Template Repository
This repository should be used as a starting point for all jobs to be run in Prefect/Python.

# What all is here?
- .github/workflows: these are GitHub action definitions that specify what happens on git push. This currently facilitates automated Docker image builds and uploads to ECR.
- images/: self explanatory.
- .dockerignore: which files/folders shouldn't be included in the Docker build. Use this to trim image size.
- .gitignore: which files/folders shouldn't be git-tracked.
- deploy.py: this is the main meat of this template - specifies how a Prefect deploy.py file should be.
- Dockerfile: the image build sequence.
- main.py: sample main file that builds a Prefect flow.
- requirements.txt: custom pip install that you want on top of codebase.
- trigger_multi_run.py: this file isn't necessary at all, but it showcases a powerful feature of new ECS deployments: distributing jobs into separate Docker containers with parameterizations. Immensely helpful for scaling, especially where we are building multiple models in one pipeline.


# Workflow

Follow these general steps to get up and running.

![Workflow](./images/workflow.drawio.svg)