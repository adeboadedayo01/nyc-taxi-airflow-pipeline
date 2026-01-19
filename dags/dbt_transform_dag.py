from airflow import DAG # type: ignore
from airflow.operators.bash import BashOperator # type: ignore
from datetime import datetime

DBT_PROJECT_DIR = "/opt/airflow/dbt_project/ny_taxi_dbt"
DBT_PROFILES_DIR = "/opt/airflow/.dbt"

with DAG(
    dag_id="dbt_transform_pipeline",
    start_date=datetime(2021, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["dbt", "warehouse"],
) as dag:

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt run --profiles-dir {DBT_PROFILES_DIR}"
        ),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt test --profiles-dir {DBT_PROFILES_DIR}"
        ),
    )

    dbt_run >> dbt_test
