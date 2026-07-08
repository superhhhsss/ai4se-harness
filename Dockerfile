FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install -e .

ENTRYPOINT ["ai4se-harness"]