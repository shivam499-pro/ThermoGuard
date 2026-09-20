FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY risk_engine ./risk_engine
COPY data ./data
COPY lambda_handlers ./lambda_handlers

# Ingress-Lambda default; Worker-Lambda overrides CMD in Terraform.
CMD ["lambda_handlers.ingress.handler"]
