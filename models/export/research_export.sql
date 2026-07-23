-- research_export
-- De-identified research product. A research export must NEVER carry a direct
-- identifier (patient_id, medical_record_number).
--
-- Planted-defect site for PHI_EXPORT_PATH (faulty only).
--
-- It carries mechanism_category together with its paired mechanism_category_missingness
-- state column (present under BOTH scenarios), demonstrating the paired-column contract
-- preserved on an export. It deliberately does not carry the raw gcs_total value, so the
-- upstream MISSINGNESS_COLLAPSE is contained to trauma_registry.

with registry as (
    select * from {{ ref('trauma_registry') }}
)

select
    registry_case_id,
    registry_site_code,

{% if var('scenario') == 'faulty' %}
    -- PLANTED DEFECT: PHI_EXPORT_PATH
    -- The direct identifier patient_id is retained in the research export select list.
    -- (In baseline it is dropped; a de-identified export must exclude direct identifiers.)
    patient_id,
{% endif %}

    -- quasi-identifier encounter timestamp (post-rename); retained but not a direct id
    ed_arrival_datetime,
    injury_datetime,

    mode_of_arrival,

    -- paired value + state column, preserved on the export under both scenarios
    mechanism_category,
    mechanism_category_missingness,

    age_at_injury_band,
    sex_at_registry_capture
from registry
