-- Singular test (both scenarios): when GCS was explicitly NOT_ASSESSED, the qualifier
-- must record a clinically coherent reason (intubated / sedated / paralyzed). This keeps
-- the synthetic seed internally consistent. Returns offending rows (none expected).
select
    registry_case_id,
    gcs_total_missingness,
    gcs_qualifier
from {{ ref('stg_ed_documentation') }}
where gcs_total_missingness = 'NOT_ASSESSED'
  and gcs_qualifier not in ('INTUBATED', 'SEDATED', 'PARALYZED')
