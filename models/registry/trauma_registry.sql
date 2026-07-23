-- trauma_registry
-- The registry model. TWO things happen here:
--
--   1. The hero migration RENAME lands here under BOTH scenarios:
--          arrival_time  ->  ed_arrival_datetime
--      (a quasi-identifier encounter timestamp; never a direct identifier).
--
--   2. Planted-defect site for MISSINGNESS_COLLAPSE (faulty only). See below.
--
-- Named-column projection so column-level lineage stays resolvable.

with registry as (
    select * from {{ ref('stg_ed_documentation') }}
)

select
    registry_case_id,
    registry_site_code,

    -- Direct identifiers still live in the registry (they are isolated at export time,
    -- not here). research_export is responsible for dropping them.
    patient_id,
    medical_record_number,

    -- THE RENAME (both scenarios): arrival_time -> ed_arrival_datetime.
    arrival_time                        as ed_arrival_datetime,
    injury_datetime,

    mode_of_arrival,

    -- mechanism_category is the always-present paired-column example: its value and its
    -- paired _missingness state column are carried through unchanged in BOTH scenarios.
    mechanism_category,
    mechanism_category_missingness,

{% if var('scenario') == 'faulty' %}
    -- PLANTED DEFECT: MISSINGNESS_COLLAPSE
    -- The >=2 distinct explicit missingness states (NOT_DOCUMENTED, NOT_ASSESSED, ...)
    -- are collapsed to a single SQL NULL, AND the paired gcs_total_missingness state
    -- column is DROPPED from the projection entirely. Downstream, a documented
    -- "not assessed" is now indistinguishable from a "not documented" or a bare null.
    -- The dropped state column is a schema-shape difference detectable from metadata
    -- alone (no need to read this SQL).
    case
        when gcs_total_missingness in ('NOT_DOCUMENTED', 'NOT_ASSESSED') then null
        else gcs_total
    end                                 as gcs_total,
    -- (gcs_total_missingness intentionally NOT selected here in faulty)
{% else %}
    -- Baseline: the value and its paired explicit-missingness state column are BOTH
    -- preserved, so every distinct controlled-vocabulary state survives downstream.
    gcs_total,
    gcs_total_missingness,
{% endif %}

    gcs_eye,
    gcs_verbal,
    gcs_motor,
    gcs_qualifier,
    age_at_injury_band,
    sex_at_registry_capture
from registry
