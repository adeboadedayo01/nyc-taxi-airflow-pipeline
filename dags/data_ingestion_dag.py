from datetime import datetime, timedelta #type: ignore
from airflow import DAG #type: ignore
from airflow.operators.bash import BashOperator #type: ignore
from airflow.operators.python import PythonOperator #type: ignore
from airflow.models import Variable #type: ignore
import pandas as pd #type: ignore
from sqlalchemy import create_engine #type: ignore
import os 
import logging

logger = logging.getLogger(__name__)

#URL_PREFIX = 'https://github.com/DataTalksClub/nyc-tlc-data/releases/download/yellow/'
#URL_TEMPLATE = URL_PREFIX + 'yellow_tripdata_{{ execution_date.strftime("%Y-%m") }}.csv.gz'
OUTPUT_DIR = '/opt/airflow/data'
#OUTPUT_FILE_TEMPLATE = OUTPUT_DIR + '/output_{{ execution_date.strftime("%Y-%m") }}.csv.gz'
TABLE_NAME = 'yellow_taxi_data'

# Database configuration - can be overridden via Airflow Variables
DB_USER = Variable.get("DB_USER", default_var="airflow")
DB_PASSWORD = Variable.get("DB_PASSWORD", default_var="airflow")
DB_HOST = Variable.get("DB_HOST", default_var="postgres")
DB_PORT = Variable.get("DB_PORT", default_var="5432")
DB_NAME = Variable.get("DB_NAME", default_var="ny_taxi")

def ensure_data_dir_exists():
    """Ensures /opt/airflow/data exists inside the container."""
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        logger.info(f"Data directory {OUTPUT_DIR} ensured")
    except Exception as e:
        logger.error(f"Failed to create data directory: {e}")
        raise

def drop_table_if_exists(**context):
    """Drops the table if it exists to avoid duplicates."""
    engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    with engine.connect() as conn:
        conn.execute(f'DROP TABLE IF EXISTS {TABLE_NAME} CASCADE')
        conn.commit()
    logger.info(f"Table {TABLE_NAME} dropped (will be recreated on first insert)")

drop_table = PythonOperator(
    task_id='drop_yellow_taxi_table',
    python_callable=drop_table_if_exists,
    retries=2,
    retry_delay=timedelta(minutes=5)
)

def ingest_to_postgres(**context):
    """Reads CSV and loads it into Postgres with error handling and chunking."""
    # Build file path from execution date (template rendering)
    execution_date = context['execution_date']
    file_path = f"{OUTPUT_DIR}/output_{execution_date.strftime('%Y-%m')}.csv.gz"
    
    try:
        # Validate file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        logger.info(f"Starting ingestion of {file_path}")
        
        # Create database connection
        connection_string = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
        engine = create_engine(connection_string)
        
        # Test connection
        with engine.connect() as conn:
            logger.info("Database connection successful")
        
        # Read and ingest data in chunks to handle large files
        chunk_size = 100000
        total_rows = 0
        
        for chunk_num, chunk_df in enumerate(pd.read_csv(file_path, compression='gzip', chunksize=chunk_size)):
            if_exists_mode = 'replace' if chunk_num == 0 else 'append'
            chunk_df.columns = [c.strip().lower() for c in chunk_df.columns]
            chunk_df.to_sql(
                TABLE_NAME, 
                con=engine, 
                if_exists=if_exists_mode,
                index=False,
                method='multi'
            )
            total_rows += len(chunk_df)
            logger.info(f"Processed chunk {chunk_num + 1}: {len(chunk_df)} rows (Total: {total_rows})")
        
        logger.info(f"Successfully ingested {total_rows} rows into {TABLE_NAME}")
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Error during ingestion: {e}")
        raise

with DAG(
    dag_id="data_ingestion_local",
    schedule="@monthly", 
    start_date=datetime(2021, 2, 1),
    end_date=datetime(2021, 3, 1),
    catchup=True,
    max_active_runs=1,
    tags=['zoomcamp'],
    description='NYC Yellow Taxi data ingestion pipeline'
) as dag:

    create_data_dir = PythonOperator(
        task_id="create_data_dir",
        python_callable=ensure_data_dir_exists,
        retries=2,
        retry_delay=timedelta(minutes=1)
    )

    

download_dataset = BashOperator(
    task_id='download_dataset',
    bash_command="""
       curl -sSL "https://github.com/DataTalksClub/nyc-tlc-data/releases/download/yellow/yellow_tripdata_{{ execution_date.strftime('%Y-%m') }}.csv.gz" \
        -o "/opt/airflow/data/output_{{ execution_date.strftime('%Y-%m') }}.csv.gz" && \
       [ -s "/opt/airflow/data/output_{{ execution_date.strftime('%Y-%m') }}.csv.gz" ] || \
           { echo "Error: Downloaded file is empty"; exit 1; }
    """,
    retries=3,
    retry_delay=timedelta(minutes=2)
)

ingest_task = PythonOperator(
    task_id='ingest_to_postgres',
    python_callable=ingest_to_postgres,
    retries=2,
    retry_delay=timedelta(minutes=5)
)

create_data_dir >> download_dataset >> ingest_task
