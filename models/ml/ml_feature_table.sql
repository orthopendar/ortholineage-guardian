-- ml_feature_table
-- Features for downstream models. Under baseline, EVERY feature derives from the
-- governed post-registry model (trauma_registry). Carries the post-rename
-- ed_arrival_datetime for a temporal feature (and for the downstream report).
--
-- Planted-defect site for UNVALIDATED_ML_SOURCE (faulty only): at least one feature is
-- sourced directly from stg_ed_documentation (the raw, "unvalidated" source), bypassing
-- trauma_registry. This changes the model's lineage — a metadata signal, no need to read
-- this SQL.

with registry as (
    select * from {{ ref('trauma_registry') }}
)

{% if var('scenario') == 'faulty' %}
-- raw, unvalidated source joined only under faulty (the bypass path)
, raw_unvalidated as (
    select
        registry_case_id,
        mode_of_arrival
    from {{ ref('stg_ed_documentation') }}
)
{% endif %}

select
    registry.registry_case_id,

    -- post-rename temporal field carried for the downstream report
    registry.ed_arrival_datetime,

    -- derived flags (no raw gcs_total value carried, so no paired-column obligation here)
    case when registry.gcs_total is null then 1 else 0 end       as gcs_missing_flag,
    case when registry.mechanism_category_missingness = 'PRESENT'
         then 1 else 0 end                                       as mechanism_present_flag,
    registry.age_at_injury_band

{% if var('scenario') == 'faulty' %}
    -- PLANTED DEFECT: UNVALIDATED_ML_SOURCE
    -- This feature is read straight from stg_ed_documentation (validation_status:
    -- unvalidated), bypassing the governed trauma_registry model.
    , raw_unvalidated.mode_of_arrival                            as raw_mode_of_arrival_feature
{% endif %}

from registry
{% if var('scenario') == 'faulty' %}
left join raw_unvalidated
    on raw_unvalidated.registry_case_id = registry.registry_case_id
{% endif %}
