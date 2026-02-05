from datetime import datetime
from airflow import DAG # type: ignore
from airflow.providers.postgres.operators.postgres import PostgresOperator # type: ignore
from airflow.providers.common.sql.operators.sql import SQLCheckOperator # type: ignore

POSTGRES_CONN_ID = "pg_ny_taxi"

with DAG(
    dag_id="warehouse_fact_trips",
    start_date=datetime(2021, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["warehouse", "dq"],
) as dag:

    create_analytics_schema_and_fact_table = PostgresOperator(
        task_id="create_analytics_schema_and_fact_table",
        postgres_conn_id=POSTGRES_CONN_ID,
        sql="""
        -- Create schema if it doesn't exist
        CREATE SCHEMA IF NOT EXISTS analytics;

        -- Create the fact table if it doesn't exist (with proper types & PK)
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
            
            -- Composite primary key to prevent accidental duplicates on re-runs
            PRIMARY KEY (trip_date, vendor_id, pickup_location_id, dropoff_location_id, payment_type)
        );
        """
    )

    # 1️⃣ Load / increment fact table
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
                '1900-01-01'
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

    # 2️⃣ DQ: fact table is not empty
    dq_row_count = SQLCheckOperator(
        task_id="dq_row_count",
        conn_id=POSTGRES_CONN_ID,
        sql="SELECT COUNT(*) > 0 FROM analytics.fact_trips;"
    )

    # 3️⃣ DQ: no NULL trip_date
    dq_no_nulls = SQLCheckOperator(
        task_id="dq_no_null_trip_date",
        conn_id=POSTGRES_CONN_ID,
        sql="""
        SELECT COUNT(*) = 0
        FROM analytics.fact_trips
        WHERE trip_date IS NULL;
        """
    )

    # 4️⃣ DQ: no duplicate grain
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

    # ✅ Task order
    create_analytics_schema_and_fact_table >> load_fact_trips >> dq_row_count >> dq_no_nulls >> dq_no_duplicates
