select
    md5(
        concat_ws(
            '||',
            coalesce(cast(vendor_id as text), ''),
            coalesce(cast(pickup_datetime as text), ''),
            coalesce(cast(dropoff_datetime as text), ''),
            coalesce(cast(pickup_location_id as text), ''),
            coalesce(cast(dropoff_location_id as text), '')
        )
    ) as trip_id,

    vendor_id,
    pickup_location_id,
    dropoff_location_id,
    pickup_datetime,
    dropoff_datetime,
    fare_amount,
    total_amount
from {{ ref('stg_yellow_taxi') }}