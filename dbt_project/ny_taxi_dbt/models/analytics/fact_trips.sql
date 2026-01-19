
select
    row_number() over (
        order by pickup_datetime, dropoff_datetime
    ) as trip_id,

    vendor_id,
    pickup_location_id,
    dropoff_location_id,
    pickup_datetime,
    dropoff_datetime,
    fare_amount,
    total_amount

from {{ ref('stg_yellow_taxi') }}

