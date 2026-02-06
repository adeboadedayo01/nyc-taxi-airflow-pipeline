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

    # 0️⃣ Create staging schema
    create_staging_schema = PostgresOperator(
        task_id="create_staging_schema",
        postgres_conn_id=POSTGRES_CONN_ID,
        sql="""
        CREATE SCHEMA IF NOT EXISTS staging;
        """
    )

    # 0.5️⃣ Create staging.stg_yellow_taxi 
    create_stg_yellow_taxi_view = PostgresOperator(
        task_id="create_stg_yellow_taxi_view",
        postgres_conn_id=POSTGRES_CONN_ID,
        sql="""
        CREATE OR REPLACE VIEW staging.stg_yellow_taxi AS
        SELECT
            vendorid             AS vendor_id,
            tpep_pickup_datetime  AS pickup_datetime,
            tpep_dropoff_datetime AS dropoff_datetime,
            pulocationid          AS pickup_location_id,
            dolocationid          AS dropoff_location_id,
            passenger_count,
            trip_distance,
            fare_amount,
            tip_amount,
            total_amount,
            payment_type
        FROM public.yellow_taxi_data
        WHERE tpep_pickup_datetime IS NOT NULL
          AND trip_distance >= 0
          AND total_amount >= 0
        ;
        """
    )

    # 1️⃣ Create analytics schema + fact table
    create_analytics_schema_and_fact_table = PostgresOperator(
        task_id="create_analytics_schema_and_fact_table",
        postgres_conn_id=POSTGRES_CONN_ID,
        sql="""
        CREATE SCHEMA IF NOT EXISTS analytics;

        CREATE TABLE IF NOT EXISTS analytics.fact_trips (
            trip_date               DATE            NOT NULL,
            vendor_id               INTEGER,
            pickup_location_id      INTEGER,
            dropoff_location_id     INTEGER,
            payment_type            INTEGER,
            
            trip_count              BIGINT          NOT NULL DEFAULT 0,
            total_passengers        BIGINT          NOT NULL DEFAULT 0,
            total_distance          DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            total_fare              DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            total_tips              DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            total_revenue           DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            
            PRIMARY KEY (trip_date, vendor_id, pickup_location_id, dropoff_location_id, payment_type)
        );
        """
    )

    # 2️⃣ Load / increment fact table
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
            SUM(passenger_count)        AS total_passengers,
            SUM(trip_distance)          AS total_distance,
            SUM(fare_amount)            AS total_fare,
            SUM(tip_amount)             AS total_tips,
            SUM(total_amount)           AS total_revenue
        FROM staging.stg_yellow_taxi
        WHERE pickup_datetime::date >
            COALESCE(
                (SELECT MAX(trip_date) FROM analytics.fact_trips),
                '1900-01-01'::date
            )
        GROUP BY
            pickup_datetime::date,
            vendor_id,
            pickup_location_id,
            dropoff_location_id,
            payment_type
        ON CONFLICT (trip_date, vendor_id, pickup_location_id, dropoff_location_id, payment_type)
        DO NOTHING;
        """
    )

    # DQ checks (unchanged)
    dq_row_count = SQLCheckOperator(
        task_id="dq_row_count",
        conn_id=POSTGRES_CONN_ID,
        sql="SELECT COUNT(*) > 0 FROM analytics.fact_trips;"
    )

    dq_no_nulls = SQLCheckOperator(
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
                vendor_id,
                pickup_location_id,
                dropoff_location_id,
                payment_type,
                COUNT(*) 
            FROM analytics.fact_trips
            GROUP BY
                trip_date,
                vendor_id,
                pickup_location_id,
                dropoff_location_id,
                payment_type
            HAVING COUNT(*) > 1
        ) t;
        """
    )

    # Task order: staging schema → staging view → analytics + table → load → DQ
    (
        create_staging_schema 
        >> create_stg_yellow_taxi_view 
        >> create_analytics_schema_and_fact_table 
        >> load_fact_trips 
        >> dq_row_count 
        >> dq_no_nulls 
        >> dq_no_duplicates
    )