# CSV Normalizer Agent (Microsoft Foundry + Python)

An AI agent that takes a **filename** from a Logic App, pulls that CSV from
**Azure Blob Storage**, uses a **Foundry-hosted model** to map its columns onto a
canonical schema and normalize dates, then writes back **two** files:

- `*_normalized.csv` — clean data, mapped to the correct columns, dates in ISO 8601.
- `*_exceptions.csv` — the source columns that didn't map to anything relevant.

A third artifact, `*_mapping_report.json`, records every decision (source →
target, confidence, reason) for auditing.

> **Runs right now with zero cloud setup.** If Azure credentials are absent the
> agent drops into a local mode (filesystem "blob" + deterministic heuristic
> mapper) so you can see the full pipeline work before provisioning anything.
> See [Working sample](#4-working-sample-offline-no-azure-needed).

---

## 1. Architecture

```
                         ┌──────────────────────────────────────────┐
   CSV dropped in Blob   │              Logic App                   │
   (or any trigger)  ───▶│  Trigger ──▶ HTTP action (POST filename) │
                         └──────────────────┬───────────────────────┘
                                            │  { "filename": "orders.csv" }
                                            ▼
                         ┌──────────────────────────────────────────┐
                         │   Agent  (FastAPI, hosted in Foundry)     │
                         │   POST /normalize                         │
                         │                                           │
                         │   1. download CSV  ◀───── Azure Blob      │
                         │   2. sample rows                          │
                         │   3. AI schema mapping ◀── Foundry model  │
                         │   4. normalize dates + numbers            │
                         │   5. split mapped / exceptions            │
                         │   6. upload outputs ─────▶ Azure Blob     │
                         └──────────────────┬───────────────────────┘
                                            │  JSON summary
                                            ▼
                         Logic App branches on status / output URIs
```

Only the **filename** travels over HTTP. The file bytes never leave Azure Blob
Storage, which keeps the Logic App payload tiny and avoids passing data through
the workflow engine.

---

## 2. The AI model

The mapping step is a **structured classification / semantic-matching** task
(“which of these known target fields, if any, does this column mean?”), not a
long-form reasoning task. The engineering-correct choice is the model that gives
the best accuracy-per-cost for that shape of work — not the largest model
available.

### Default: **`gpt-4.1-mini`** (deployed via Microsoft Foundry / Azure OpenAI)

| Property | Value |
|---|---|
| Family | OpenAI GPT-4.1 |
| Deployment | Microsoft Foundry (Azure OpenAI) — you create a *deployment name* |
| Why this one | Outperforms `gpt-4o-mini` on instruction-following and long-context; strong at strict JSON output; roughly an order of magnitude cheaper than the flagship tier, which matters when you may re-map thousands of files |
| Context | Long context (handles wide CSVs with many columns + samples comfortably) |
| Output mode used | `response_format={"type": "json_object"}` at `temperature=0` for deterministic, parseable mappings |
| Auth | API key **or** Managed Identity (recommended) |

### When to size up

Swap the deployment name (env var `AZURE_OPENAI_DEPLOYMENT`) — no code change:

- **`gpt-4.1`** — messier headers, cryptic abbreviations, or many near-duplicate
  target fields where you want maximum mapping accuracy.
- **`gpt-5`** (or the current flagship in your Foundry catalog) — highest-stakes
  feeds where a mis-map is expensive and native reasoning + tool use is worth the
  cost. Overkill for clean data.
- **`gpt-4.1-nano`** — very high volume, very simple headers, cost-first.

> Model availability changes over time and by region. Check your own catalog in
> Foundry (Model catalog → filter *Agent supported*) and confirm the deployment
> name you set here exists in your resource. Pricing shifts too — verify on the
> Azure OpenAI pricing page before committing to a tier.

Because the mapper is behind a small interface, the model is a **configuration
choice**, and a deterministic offline mapper is always available as a fallback.

---

## 3. Project layout

```
csv-normalizer-agent/
├── README.md
├── requirements.txt
├── Dockerfile
├── .env.example
├── config/
│   └── schema_mapping.json        # canonical target schema (edit this)
├── src/
│   ├── app.py                     # FastAPI /normalize endpoint (Logic App calls this)
│   ├── agent.py                   # orchestration: download → map → normalize → upload
│   ├── ai_mapper.py               # Foundry mapper + offline heuristic mapper
│   ├── date_normalizer.py         # date parsing → ISO 8601
│   ├── blob_storage.py            # Azure Blob + local filesystem backends
│   └── config.py                  # env-driven settings
├── sample_data/
│   └── orders_sample.csv          # deliberately messy demo file
├── logicapp/
│   └── workflow.sample.json       # example Logic App workflow
└── tests/
    └── run_sample.py              # runs the whole pipeline offline
```

---

## 4. Working sample (offline, no Azure needed)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # or just: pip install pandas python-dateutil
python -m tests.run_sample
```

The sample maps this messy input:

```
Order No, Client Name, E-mail, Placed On, Shipped, Grand Total, CCY, Qty,
Order Status, Ship Country, Sales Rep, Internal Notes
```

into a clean, canonical file and an exceptions file:

**`orders_sample_normalized.csv`**
```
order_id,customer_name,email,order_date,ship_date,amount,currency,quantity,status,country
SO-1001,Acme Corp,billing@acme.com,2025-03-15,2025-03-18,1250.0,USD,5,Shipped,United States
SO-1002,Beta Retail,ap@betaretail.co,2025-03-15,2025-03-18,980.5,EUR,3,Delivered,Germany
...
SO-1005,Epsilon GmbH,,2025-03-17,2025-03-20,2310.75,EUR,7,Cancelled,Austria
```

**`orders_sample_exceptions.csv`** (columns with no relevant target)
```
Sales Rep,Internal Notes
J. Cruz,priority client
M. Reyes,
...
```

Notice what the pipeline handled: mixed date formats (`03/15/2025`, `15/03/2025`,
`2025/03/16`, `March 17 2025`, `17.03.2025`) all normalized to ISO 8601 —
including day-first inference for `15/03/2025` — and currency-formatted amounts
(`$1,250.00`, `2.310,75`, `₱54,300.00`) cleaned to plain numbers.

---

## 5. Deploying to Azure

### 5.1 Deploy the model in Foundry
1. Open **Microsoft Foundry** → your project → **Model catalog**.
2. Deploy **`gpt-4.1-mini`** (or your chosen model). Note the **deployment name**.
3. Copy the resource **endpoint** (`https://<resource>.openai.azure.com/`).

### 5.2 Blob Storage
Create a storage account with two containers (defaults): `incoming` and
`normalized`. Grant the agent's identity **Storage Blob Data Contributor**, or
use a connection string.

### 5.3 Host the agent
Build and push the container, then run it as a Foundry-hosted / Azure Container
App / managed online endpoint:

```bash
docker build -t csv-normalizer-agent .
# push to your registry, then deploy the image with the env vars from §6
```

Health check: `GET /health` → shows engine (`foundry`/`heuristic`), blob mode,
and the active deployment name.

### 5.4 Wire up the Logic App
Use `logicapp/workflow.sample.json` as a starting point. The key action is an
**HTTP POST** to the agent:

```json
{
  "method": "POST",
  "uri": "https://<your-endpoint>/normalize",
  "headers": { "Content-Type": "application/json" },
  "body": { "filename": "@triggerBody()?['Name']" }
}
```

Then branch on `@body('Call_Normalizer_Agent')?['status']`.

---

## 6. Configuration (environment variables)

| Variable | Purpose | Default |
|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | Foundry/Azure OpenAI endpoint | *(empty → offline mapper)* |
| `AZURE_OPENAI_DEPLOYMENT` | Model **deployment** name | `gpt-4.1-mini` |
| `AZURE_OPENAI_API_VERSION` | API version | `2024-10-21` |
| `AZURE_OPENAI_API_KEY` | Optional; omit to use Managed Identity | *(empty)* |
| `AZURE_STORAGE_CONNECTION_STRING` | Blob auth (option A) | *(empty → local blob)* |
| `AZURE_STORAGE_ACCOUNT_URL` | Blob auth (option B, + Managed Identity) | *(empty)* |
| `INPUT_CONTAINER` | Where source CSVs live | `incoming` |
| `OUTPUT_CONTAINER` | Where outputs are written | `normalized` |
| `SCHEMA_PATH` | Path to the schema JSON | `config/schema_mapping.json` |
| `SAMPLE_ROWS_FOR_AI` | Sample values per column sent to the model | `8` |
| `FORCE_LOCAL` | Force offline mode | `false` |

The agent auto-selects **Azure** backends when the relevant vars are set and
**local** backends otherwise — so the same image runs the sample and production.

---

## 7. The schema mapping file (`config/schema_mapping.json`)

This is the contract you edit to fit your domain. Each target field has:

| Key | Meaning |
|---|---|
| `target` | Canonical output column name |
| `type` | `string` \| `date` \| `number` \| `integer` — drives normalization |
| `required` | Documented expectation (surfaced in the report) |
| `aliases` | Known alternative header names — helps both the model and the offline mapper |
| `description` | Natural-language hint the model uses for semantic matching |

Top-level knobs: `date_output_format` (default `%Y-%m-%d`) and
`matching.confidence_threshold` (default `0.60`) — columns mapped below this
confidence are demoted to exceptions.

To adapt to a new file type, **just edit this JSON** — no code changes.

---

## 8. API reference

### `POST /normalize`
```json
// request
{ "filename": "orders_2025_03.csv" }
```
```json
// response
{
  "status": "success",
  "input_file": "orders_2025_03.csv",
  "normalized_blob": "https://.../normalized/orders_2025_03_normalized.csv",
  "exceptions_blob": "https://.../normalized/orders_2025_03_exceptions.csv",
  "report_blob":     "https://.../normalized/orders_2025_03_mapping_report.json",
  "engine": "foundry",
  "rows": 1240,
  "mapped_columns": { "Order No": "order_id", "...": "..." },
  "exception_columns": ["Sales Rep", "Internal Notes"],
  "date_parse_failures": {},
  "message": "Mapped 10 column(s); 2 exception column(s)."
}
```
`404` if the blob is missing, `500` on processing errors (message included so the
Logic App can log/branch).

### `GET /health`
Returns current engine, blob mode, and deployment name.

---

## 9. How normalization works

- **Dates** — a set of explicit formats is tried first (fast, deterministic),
  then `dateutil` as a fallback. Ambiguous `DD/MM` vs `MM/DD` columns are
  resolved with a per-column `dayfirst` hint inferred from the samples (if any
  value has a first component > 12, day is first). Unparseable values are left
  intact and **counted** in `date_parse_failures` rather than silently dropped.
- **Numbers** — currency symbols, spaces and letters are stripped. When both
  `.` and `,` are present, the right-most is treated as the decimal separator, so
  both `1,250.00` → `1250.0` and `2.310,75` → `2310.75` come out correctly.

---

## 10. Known limitations

- **Single-separator number locale ambiguity.** A lone comma (e.g. `1,050`) is
  treated as a thousands separator (US/feed default). A value that is genuinely
  `1,05` (European “one point oh five”) would be read as `105`. Disambiguate per
  feed if your sources use comma-decimals without a thousands separator.
- **Row-level exceptions vs column-level.** Exceptions here are **columns** that
  don't map. If you also need to quarantine individual bad *rows* (e.g. failed
  date parses), extend `agent.py` to split rows using `date_parse_failures`.
- **One target per column.** The agent enforces a 1:1 mapping; if two source
  columns both look like `amount`, the higher-confidence one wins and the other
  becomes an exception. Split into separate target fields if you need both.
- **Model/region drift.** Deployment names, model availability and pricing change
  over time — confirm against your live Foundry catalog.

---

## 11. Extending

- Add target fields by editing `config/schema_mapping.json`.
- Point at a different model with `AZURE_OPENAI_DEPLOYMENT`.
- Add a new blob/store backend by implementing the tiny `BlobStore` protocol.
- Add per-row quarantine, dead-lettering, or a review queue in `agent.py`.
```
