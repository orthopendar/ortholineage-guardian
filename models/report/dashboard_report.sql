-- dashboard_report
-- Summary surface over the ML feature table. The migration renamed
-- arrival_time -> ed_arrival_datetime upstream; baseline uses the new name.
--
-- Planted-defect site for STALE_REFERENCE (faulty only): this report still exposes the
-- pre-rename name `arrival_time` — the half-completed migration. The column-name
-- reappearance is a lineage/naming inconsistency detectable from metadata (no need to
-- read this SQL).

with features as (
    select * from {{ ref('ml_feature_table') }}
)

select
    count(*)                    as case_count,
    sum(gcs_missing_flag)       as gcs_missing_count,
    sum(mechanism_present_flag) as mechanism_present_count,

{% if var('scenario') == 'faulty' %}
    -- PLANTED DEFECT: STALE_REFERENCE
    -- Still exposes the pre-rename name `arrival_time` even though trauma_registry
    -- renamed it to ed_arrival_datetime. The stale name reappears downstream.
    max(ed_arrival_datetime)    as arrival_time
{% else %}
    -- post-rename name used correctly
    max(ed_arrival_datetime)    as ed_arrival_datetime
{% endif %}

from features
