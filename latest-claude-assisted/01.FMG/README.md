# README — AI-Assisted Schema Mapping for NEO & LAO

This package builds an **AI-assisted schema-mapping** step that takes a customer's
Excel workbook and maps its columns onto the canonical fields required to produce the
**NEO** and **LAO** CSV outputs, giving a **confidence score per column** (target
70–90%). It is designed to sit *in front of* your existing `NEO.py` / `LAO.py`
pipeline. No Snowflake logic is included (that is your later integration step).

## What's in the box

| File | Purpose |
|---|---|
| `SCHEMA_MAPPING_PROMPT.md` | The prompt (system + user) for the AI agent, plus model & settings. |
| `SCHEMA_MAPPING_RESULTS.md` | The actual mapping run + confidence score for every column. |
| `NEO_mapped.csv` | NEO output produced by the mapping (validation run). |
| `LAO_mapped.csv` | LAO output produced by the mapping (validation run). |
| `Normalized.csv` | Rows that couldn't be processed (no key / gibberish / banner rows). |
| `mp_confidence.csv`, `ltp_confidence.csv` | Machine-readable confidence tables. |

## The problem, stated precisely

1. A customer uploads an Excel with several sheets. For **this** customer the useful
   sheets are **LTP** (tab is literally named `CB MM LTP`) and **Measurement Points**.
   The sheet list is a **config array**, so new customers/sheets are added later
   without code changes.
2. The **LTP** sheet feeds the **NEO** CSV. The columns NEO needs are defined by
   `NEO.py`.
3. The **Measurement Points** sheet feeds the **LAO** CSV. The columns LAO needs are
   defined by `LAO.py`.
4. Output must be **NEO.csv** and **LAO.csv** in the exact structure of the reference
   files `FMG_NEO_Aug_26.csv` and `FMG_LAO_Aug_26.csv`.
5. Any row with **no key / gibberish / unprocessable** data goes to **Normalized.csv**.

## The one thing you must understand about the data

`NEO.py` and `LAO.py` do **not** run on the customer Excel directly. They run on a
DataFrame that has already been **merged** with internal reference data — AMT, the
Cross-Reference (Xref), and IK17. That is why the code refers to columns like
`Equipment_y`, `Model_y`, `Serial_Number_y`, `Component_Code_y`, `Primary_Part_Number`,
`Sales_Status`, etc. The `_y` suffix is a pandas merge artifact — **those columns are
not in the customer workbook.**

Consequences, and how this package handles them honestly:

- The customer Excel supplies a **subset** of the NEO/LAO columns directly — chiefly
  the asset/model identity, the schedule dates, the task description, the strategy
  interval, and (for LAO) the measurement/counter fields plus the **Functional
  Location join key**.
- Every other NEO/LAO column is **enrichment** (it arrives from the AMT/Xref/IK17
  join later). Per your rule *"do not invent columns,"* these are emitted **empty**
  and labelled `requires_enrichment` — never fabricated.
- The reference FMG CSVs are a **different customer** (Fortescue). They are used only
  to lock the **output column set and order** — not as an answer key of values.

## How the mapping works (what the prompt tells the agent to do)

1. **Sheet detection (flexible).** A `sheet_config` array maps a *role* (`LTP`,
   `MEASUREMENT_POINTS`) to name patterns. Matching is case-insensitive substring, so
   `CB MM LTP` matches the `ltp` pattern. Add customers by appending entries.
2. **Column profiling.** For each column: read the header and sample the values.
3. **Scoring (hybrid, deterministic core).** For each canonical field, score every
   candidate column:
   - `name_score` = alias similarity (string ratio + token overlap),
   - `value_score` = fraction of values matching the field's dtype/format,
   - `+ join bonus` for the Functional-Location key (overlap with Measurement Points),
   - `confidence = 0.6·name + 0.4·value` (+ join bonus, capped 0.99).
   Columns are then assigned **greedily, one-to-one** (highest score first) so two
   fields can't grab the same source column.
4. **Verdict bands.** ≥0.90 auto-accept · 0.70–0.89 accept-with-review · 0.50–0.69
   low/review · <0.50 reject.
5. **Row routing.** Missing join key, missing identity, banner/blank rows, or
   gibberish → `Normalized.csv` with a `_reject_reason`. Everything else → NEO/LAO.
6. **Emit** the `mapping_report` JSON (confidence per column) and write the three CSVs.

**Why hybrid and not pure-LLM:** the confidence numbers are *computed* by a small
deterministic function so they're reproducible and defensible. The LLM does what it's
good at — recognising that `Meas/TotCountrRdg   _` means "measured total counter
reading", or that a `Type` column polluted with `All - Ancillary` should be flagged.

## Results summary (see `SCHEMA_MAPPING_RESULTS.md` for the full table)

| Scope | Columns mapped | Mean confidence | In 0.70–0.99 |
|---|---:|---:|---:|
| Measurement Points → LAO | 6 | **0.99** | 6 / 6 |
| CB MM LTP → NEO | 10 | **0.82** | 8 / 10 |
| Combined mappable | 16 | **0.88** | 14 / 16 |

Two columns land below 0.70 on purpose — `ModelCode←Type` (0.65) and
`Task_Counter←Group Counter` (0.69) — because those source columns are genuinely mixed
in content. Flagging them beats inflating them.

Validation-run row counts: **NEO 9,296 · LAO 22,893 · Normalized 1,403.**

## Recommended model

- **Default:** current-generation **Claude Sonnet**, `temperature=0`, structured
  (tool-use/JSON-schema) output.
- **Escalate only the 0.50–0.69 columns** to current-generation **Claude Opus** for a
  second opinion.
- **Avoid** Haiku for the mapping decision (too shallow for alias disambiguation).
- Keep the numeric scorer in code; let the model own alias reasoning and edge-case notes.

## How to run it against a new customer

1. Add the customer's sheets to `sheet_config` if their tab names differ.
2. Point the user prompt at the new `.xlsx` and paste the NEO/LAO reference headers.
3. Review any column with confidence < 0.90 (the report lists them).
4. Pass `NEO.csv` / `LAO.csv` to your existing pipeline; the enrichment columns fill
   in during the AMT/Xref/IK17 join.

## Deliberate non-goals

- **No Snowflake / warehouse** anything — file output only, as requested.
- **No invented columns or values** — enrichment fields stay empty and labelled.
- **No new columns** outside the fixed NEO (29) / LAO (27) layouts.
