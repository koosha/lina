FROM public.ecr.aws/lambda/python:3.12

# psycopg2-binary at runtime needs libpq from postgresql-libs.
RUN dnf install -y postgresql-libs && dnf clean all

# Install Python dependencies first so they cache between source changes.
COPY deploy/lambda/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy LINA source onto the Lambda task root so packages are importable.
COPY src/ ${LAMBDA_TASK_ROOT}/

# Copy the entry shim that re-exports lina_supervisor.lambda_handler.handler.
COPY deploy/lambda/lambda_handler.py ${LAMBDA_TASK_ROOT}/lambda_handler.py

CMD ["lambda_handler.handler"]
