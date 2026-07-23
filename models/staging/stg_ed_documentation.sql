-- stg_ed_documentation
-- Staging over the raw, "unvalidated" ED documentation source. This is the pre-rename
-- world: it still carries `arrival_time` (renamed to `ed_arrival_datetime` downstream in
-- trauma_registry), the direct identifiers as captured at intake, and BOTH paired
-- value + <field>_missingness columns exactly as documented.
--
-- Named-column projection (no SELECT *) so column-level lineage is resolvable downstream.
-- This model is identical under both scenarios; no planted defects live here.

with source as (
    select * from {{ ref('ed_documentation_raw') }}
)

select
    registry_case_id,
    registry_site_code,
    patient_id,
    medical_record_number,
    cast(arrival_time as timestamp)     as arrival_time,
    cast(injury_datetime as timestamp)  as injury_datetime,
    mode_of_arrival,
    mechanism_category,
    mechanism_category_missingness,
    try_cast(gcs_total as integer)      as gcs_total,
    gcs_total_missingness,
    try_cast(gcs_eye as integer)        as gcs_eye,
    try_cast(gcs_verbal as integer)     as gcs_verbal,
    try_cast(gcs_motor as integer)      as gcs_motor,
    gcs_qualifier,
    age_at_injury_band,
    sex_at_registry_capture
from source
