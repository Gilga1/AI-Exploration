# Registry

YAML metadata files bootstrap the Neo4j knowledge graph on startup (when `AUTO_PUBLISH_REGISTRY=true`) or via:

```bash
cd backend && source .venv/bin/activate
python -m scripts.bootstrap_graph
```

## Folder layout

| Folder | `kind` | Purpose |
|---|---|---|
| `data_sources/` | `data_source` | Physical tables/views, columns, joins, grain |
| `measures/` | `measure` | Parameterized SQL fragments; **`depends_on`** → data sources |
| `metrics/` | `metric` | Composed KPIs; **`components`** + optional **`depends_on`** → measures/metrics |
| `entities/` | `entity` | Business glossary + `resolves_via` name→ID lookup |
| `validation_policies/` | `validation_policy` | Post-query validation rules linked to metrics |

## Dependency model

- **Measures** declare `depends_on` → `data_source` (which tables the SQL reads).
- **Metrics** declare `components` (numerator/denominator → measures or nested metrics) for composition edges (`USES_COMPONENT`).
- **Metrics** also declare `depends_on` listing the same measures — explicit lineage for validation and audit.
- **Columns** may set `entity_ref: fund` to create `REPRESENTS` edges to Entity nodes on publish.

## Pilot samples

| File | Description |
|---|---|
| `data_sources/fct_fund_transactions.yaml` | Transaction fact |
| `data_sources/dim_fund.yaml` | Fund dimension |
| `data_sources/fct_daily_fund_balances.yaml` | Daily balance fact |
| `measures/total_transaction_amount_by_fund_day.yaml` | Rollup measure |
| `measures/average_daily_balance_by_fund_day.yaml` | Balance measure |
| `metrics/net_flow_ratio.yaml` | Ratio metric |
| `entities/fund.yaml`, `product.yaml`, `share_class.yaml`, … | Entity catalog (7+ types) |
| `validation_policies/net_flow_ratio_validation.yaml` | YAML validation rules for pilot metric |

## Authoring notes

- Quote the join `on` field in YAML: `"on": "fund_id = fund_id"` (bare `on` parses as boolean).
- Filenames should match `metadata.id` (snake_case).
- Run validation before publish: `POST /api/v1/registry/validate`
