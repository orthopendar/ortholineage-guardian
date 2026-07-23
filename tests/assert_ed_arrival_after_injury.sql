-- Singular test (both scenarios): temporal integrity — ED arrival must not precede the
-- injury time. Exercises the post-rename ed_arrival_datetime name in the registry.
-- Returns offending rows (none expected).
select
    registry_case_id,
    ed_arrival_datetime,
    injury_datetime
from {{ ref('trauma_registry') }}
where ed_arrival_datetime is not null
  and injury_datetime is not null
  and ed_arrival_datetime < injury_datetime
