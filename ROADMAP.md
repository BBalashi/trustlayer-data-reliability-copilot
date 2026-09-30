# TrustLayer roadmap

The current release is deliberately local, free, and small enough to understand in one sitting. The priorities below extend the working seams already present rather than replacing the MVP with speculative infrastructure.

## Near term

- Add a versioned data-contract file so schema and thresholds can be reviewed without code changes.
- Retain historical clean snapshots behind a configurable limit for deeper root-cause comparisons.
- Add station/code drill-downs and links to TTC delay-code reference material.
- Replace mean-only distribution drift with PSI or Wasserstein distance plus minimum sample guards.
- Make freshness policy resource-metadata aware, separating publisher lag from cache lag.
- Add atomic cache promotion with checksum and schema validation before replacing the last known-good sample.

## Operational maturity

- Add a lightweight local scheduler and notification adapter while preserving the CLI.
- Support configurable incident ownership, acknowledgements, and resolution notes.
- Add structured logging, pipeline duration metrics, and an execution-error table.
- Add migration/version handling for the DuckDB schema.
- Package the project for one-command installation and add CI for Python 3.11–3.13.

## Extensibility

- Implement additional dataset adapters behind the ingestion interface.
- Add a strictly optional LLM explanation provider selected only when an environment variable is present; retain deterministic fallback and never require a secret.
- Add a rule registry so new checks can be configured per dataset.
- Add exportable incident reports and machine-readable quality results.

## Deliberately deferred

Kafka, Airflow, Spark, Kubernetes, and cloud warehouses are not justified by this local MVP's scale. They would be considered only after a real workload demonstrates the need for distributed ingestion, orchestration, compute, or deployment.
