{{ config(materialized='view') }}

select
    vendorid as vendor_id,
    tpep_pickup_datetime as pickup_datetime,
    tpep_dropoff_datetime as dropoff_datetime,
    pulocationid as pickup_location_id,
    dolocationid as dropoff_location_id,
    passenger_count,
    trip_distance,
    fare_amount,
    tip_amount,
    total_amount,
    payment_type
from {{ source('raw', 'yellow_taxi_data') }}

