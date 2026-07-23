-- dq_metrics
-- Data-quality / completeness + temporal-integrity metrics over the registry.
-- Reads the POST-rename `ed_arrival_datetime` (never the stale `arrival_time`) — a
-- downstream witness that the migration name is used correctly here under both
-- scenarios. Carries no direct identifiers. Derives completeness from value presence
-- and the surviving mechanism_category_missingness state column, so it needs no
-- gcs_total_missingness dependency and is identical under both scenarios.

with registry as (
    select * from {{ ref('trauma_registry') }}
)

select
    registry_case_id,
    registry_site_code,

    -- post-rename timestamp used correctly (temporal-integrity input)
    ed_arrival_datetime,
    injury_datetime,

    -- temporal integrity: arrival should not precede injury
    case
        when ed_arrival_datetime is not null
             and injury_datetime is not null
             and ed_arrival_datetime >= injury_datetime
        then 1 else 0
    end                                                     as arrival_after_injury_flag,

    -- completeness of the GCS value (bare-value presence)
    case when gcs_total is not null then 1 else 0 end       as gcs_value_present_flag,

    -- completeness of mechanism, read from the surviving paired state column
    case when mechanism_category_missingness = 'PRESENT' then 1 else 0 end
                                                            as mechanism_present_flag,
    mechanism_category_missingness
from registry
