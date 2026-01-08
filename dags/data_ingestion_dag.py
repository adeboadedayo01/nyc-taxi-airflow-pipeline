from datetime import datetime, timedelta
from airflow import DAG  # type: ignore
from airflow.operators.bash import BashOperator # type: ignore
from airflow.operators.python import PythonOperator # type: ignore
from airflow.providers.postgres.hooks.postgres import PostgresHook # type: ignore
import pandas as pd # type: ignore
import os
import logging

logger = logging.getLogger(__name__)

OUTPUT_DIR = "/opt/airflow/data"
TABLE_NAME = "yellow_taxi_data"
POSTGRES_CONN_ID = "pg_ny_taxi"


def ensure_data_dir_exists():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def ingest_to_postgres(**context):
    logical_date = context["logical_date"]
    file_path = f"{OUTPUT_DIR}/output_{logical_date.strftime('%Y-%m')}.csv.gz"

    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)

    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    engine = hook.get_sqlalchemy_engine()

    chunk_size = 100_000
    total_rows = 0

    for chunk in pd.read_csv(file_path, compression="gzip", chunksize=chunk_size):
        chunk.columns = (
            chunk.columns
            .str.strip()
            .str.lower()
        )

        chunk.to_sql(
            TABLE_NAME,
            con=engine,
            if_exists="append",
            index=False,
            method="multi"
        )

        total_rows += len(chunk)

    logger.info(f"Loaded {total_rows} rows into {TABLE_NAME}")


with DAG(
    dag_id="data_ingestion_local",
    schedule="@monthly",
    start_date=datetime(2021, 1, 1),
    end_date=datetime(2021, 3, 1),
    catchup=True,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=3),
    },
    tags=["zoomcamp"],
) as dag:

    create_data_dir = PythonOperator(
        task_id="create_data_dir",
        python_callable=ensure_data_dir_exists,
    )

    download_dataset = BashOperator(
        task_id="download_dataset",
        bash_command="""
        curl -sSL \
        "https://github.com/DataTalksClub/nyc-tlc-data/releases/download/yellow/yellow_tripdata_{{ logical_date.strftime('%Y-%m') }}.csv.gz" \
        -o "/opt/airflow/data/output_{{ logical_date.strftime('%Y-%m') }}.csv.gz"
        """,
    )

    ingest_task = PythonOperator(
        task_id="ingest_to_postgres",
        python_callable=ingest_to_postgres,
        retries=2,
        retry_delay=timedelta(minutes=5)
    )

    create_data_dir >> download_dataset >> ingest_task
