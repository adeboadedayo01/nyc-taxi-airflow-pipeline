from datetime import datetime
from airflow import DAG #type: ignore
from airflow.providers.postgres.operators.postgres import PostgresOperator #type: ignore
from airflow.providers.common.sql.operators.sql import SQLCheckOperator #type: ignore

POSTGRES_CONN_ID = "pg_ny_taxi"

with DAG(
    dag_id="warehouse_fact_trips",
    start_date=datetime(2021, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["warehouse", "dq"],
    max_active_runs=1,
) as dag:

    # ──────────────────────────────────────────────────────────────
    # 0. Prepare staging schema & view
    # ──────────────────────────────────────────────────────────────

    create_staging_schema = PostgresOperator(
        task_id="create_staging_schema",
        postgres_conn_id=POSTGRES_CONN_ID,
        sql="CREATE SCHEMA IF NOT EXISTS staging;"
    )

    create_stg_yellow_taxi_view = PostgresOperator(
        task_id="create_stg_yellow_taxi_view",
        postgres_conn_id=POSTGRES_CONN_ID,
        sql="""
        CREATE OR REPLACE VIEW staging.stg_yellow_taxi AS
        SELECT
            vendorid                    AS vendor_id,
            tpep_pickup_datetime::date  AS trip_date,
            pulocationid                AS pickup_location_id,
            dolocationid                AS dropoff_location_id,
            passenger_count,
            trip_distance,
            fare_amount,
            tip_amount,
            total_amount,
            payment_type
        FROM public.yellow_taxi_data
        WHERE tpep_pickup_datetime IS NOT NULL
          AND trip_distance     >= 0
          AND total_amount      >= 0;
        """
    )

    # ──────────────────────────────────────────────────────────────
    # 1. Create target schema & fact table
    # ──────────────────────────────────────────────────────────────

    create_analytics_schema_and_fact_table = PostgresOperator(
    task_id="create_analytics_schema_and_fact_table",
    postgres_conn_id=POSTGRES_CONN_ID,
    sql="""
   
    DROP TABLE IF EXISTS analytics.fact_trips;

    CREATE SCHEMA IF NOT EXISTS analytics;

    CREATE TABLE analytics.fact_trips (
        trip_date               DATE             NOT NULL,
        vendor_id               INTEGER,                         -- nullable
        pickup_location_id      INTEGER,
        dropoff_location_id     INTEGER,
        payment_type            INTEGER,

        passenger_count         INTEGER          NOT NULL DEFAULT 0,
        trip_distance           DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        fare_amount             DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        tip_amount              DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        total_amount            DOUBLE PRECISION NOT NULL DEFAULT 0.0,

        PRIMARY KEY (trip_date, pickup_location_id, dropoff_location_id)
    );
    """
)

    # ──────────────────────────────────────────────────────────────
    # 2. Incremental load into fact table
    # ──────────────────────────────────────────────────────────────

    load_fact_trips = PostgresOperator(
    task_id="load_fact_trips",
    postgres_conn_id=POSTGRES_CONN_ID,
    sql="""
    INSERT INTO analytics.fact_trips (
        trip_date,
        vendor_id,
        pickup_location_id,
        dropoff_location_id,
        payment_type,
        trip_count,
        total_passengers,
        total_distance,
        total_fare,
        total_tips,
        total_revenue
    )
    SELECT
        pickup_datetime::date       AS trip_date,
        vendor_id,
        pickup_location_id,
        dropoff_location_id,
        payment_type,
        COUNT(*)                    AS trip_count,
        COALESCE(SUM(passenger_count), 0)   AS total_passengers,
        COALESCE(SUM(trip_distance),   0.0) AS total_distance,
        COALESCE(SUM(fare_amount),     0.0) AS total_fare,
        COALESCE(SUM(tip_amount),      0.0) AS total_tips,
        COALESCE(SUM(total_amount),    0.0) AS total_revenue
    FROM staging.stg_yellow_taxi
    WHERE pickup_datetime::date >= COALESCE(
        (SELECT MAX(trip_date) FROM analytics.fact_trips),
        '1900-01-01'::date
    )
    GROUP BY
        pickup_datetime::date,
        vendor_id,
        pickup_location_id,
        dropoff_location_id,
        payment_type
    ON CONFLICT (trip_date, pickup_location_id, dropoff_location_id)
    DO NOTHING;
    """
)

    # ──────────────────────────────────────────────────────────────
    # 3. Data Quality Checks
    # ──────────────────────────────────────────────────────────────

    dq_row_count = SQLCheckOperator(
        task_id="dq_row_count",
        conn_id=POSTGRES_CONN_ID,
        sql="SELECT COUNT(*) > 0 FROM analytics.fact_trips;"
    )

    dq_no_null_trip_date = SQLCheckOperator(
        task_id="dq_no_null_trip_date",
        conn_id=POSTGRES_CONN_ID,
        sql="""
        SELECT COUNT(*) = 0
        FROM analytics.fact_trips
        WHERE trip_date IS NULL;
        """
    )

    dq_no_duplicates = SQLCheckOperator(
        task_id="dq_no_duplicates",
        conn_id=POSTGRES_CONN_ID,
        sql="""
        SELECT COUNT(*) = 0
        FROM (
            SELECT
                trip_date,
                pickup_location_id,
                dropoff_location_id,
                payment_type,
                COUNT(*) AS trip_count 
            FROM analytics.fact_trips
            GROUP BY trip_date, pickup_location_id, dropoff_location_id, payment_type
            HAVING COUNT(*) > 1
        ) AS duplicates;
        """
    )

    # ──────────────────────────────────────────────────────────────
    # Execution order
    # ──────────────────────────────────────────────────────────────

    (
        create_staging_schema
        >> create_stg_yellow_taxi_view
        >> create_analytics_schema_and_fact_table
        >> load_fact_trips
        >> dq_row_count
        >> dq_no_null_trip_date
        >> dq_no_duplicates
    )