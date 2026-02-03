
select
    vendorid as vendor_id,
    tpep_pickup_datetime as pickup_datetime,
    tpep_dropoff_datetime as dropoff_datetime,
    pulocatioid as pickup_location_id,
    dolocatioid as dropoff_location_id,
    passenger_count as passenger_count,
    trip_distance as trip_distance,
    fare_amount as fare_amount,
    tip_amount as tip_amount,
    total_amount as total_amount,
    payment_type as payment_type
from {{ source('raw', 'yellow_taxi_data') }}

