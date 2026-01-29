FROM apache/airflow:2.7.3

USER airflow

RUN pip install --no-cache-dir dbt-postgres==1.7.4
RUN apt-get update && apt-get install -y git