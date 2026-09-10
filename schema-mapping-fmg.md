# Build and validate AI-ready FMG schema-mapping business-rule artifacts.
import json

mappings = [
 {"target":"BranchCode","source":"constant/location array","rule":"Set from the FMG location configuration; current stated value is WA-FMG.","status":"provisional"},
 {"target":"SiteCode","source":None,"rule":"Do not infer; require Forecasting Officer or configuration input.","status":"unresolved"},
 {"target":"FleetCode","source":None,"rule":"Do not infer; require Forecasting Officer or configuration input.","status":"unresolved"},
 {"target":"CustomerCode","source":"AMT.CUSTOMER","rule":"Lookup AMT by normalized LTP serial/equipment number and return CUSTOMER.","status":"confirmed"},
 {"target":"ModelCode","source":"LTP.Type (A)","rule":"Direct map after trimming whitespace.","status":"confirmed"},
 {"target":"AssetName","source":["LTP.Equipment (E)","SerialNumber"],"rule":"Concatenate normalized equipment identifier and serial number using the configured separator.","status":"confirmed"},
 {"target":"SerialNumber","source":"LTP.Equipment (E)","rule":"Use the LTP equipment number as SerialNumber; preserve as text.","status":"confirmed"},
 {"target":"RegistrationCounter","source":None,"rule":"Do not infer; require Forecasting Officer or configuration input.","status":"unresolved"},
 {"target":"ComponentCode","source":"AMT.COMPONENT_CODE","rule":"Lookup AMT by normalized SerialNumber.","status":"confirmed"},
 {"target":"ModifierCode","source":"AMT.MODIFIER_CODE","rule":"Lookup AMT by normalized SerialNumber.","status":"confirmed"},
 {"target":"TaskTypeCode","source":"AMT.TASK_TYPE","rule":"Lookup AMT by normalized SerialNumber.","status":"confirmed"},
 {"target":"TaskCounterCode","source":"AMT.JOB_CODE","rule":"Lookup AMT by normalized SerialNumber.","status":"confirmed"},
 {"target":"StrategyTaskDescription","source":"AMT.ST_DESCRIPTION","rule":"Lookup AMT by normalized SerialNumber.","status":"confirmed"},
 {"target":"FrequencyValue","source":"LTP.Strategy (P)","rule":"Direct map; parse as numeric where valid.","status":"confirmed"},
 {"target":"LifeToDateValue","source":"LTP.Counter reading","rule":"Direct map; parse as numeric and retain zero as a valid value.","status":"confirmed"},
 {"target":"PrimaryPartNumberCode","source":"AMT.PRIMARY_PART_NUMBER","rule":"Lookup AMT by normalized SerialNumber.","status":"confirmed"},
 {"target":"NextPartNumberCode","source":"AMT.NEXT_PART_NUMBER","rule":"Lookup AMT by normalized SerialNumber.","status":"confirmed"},
 {"target":"SourceOfSupplyCode","source":None,"rule":"Do not infer; require Forecasting Officer or configuration input.","status":"unresolved"},
 {"target":"StrategyUOMCode","source":None,"rule":"Do not infer; require Forecasting Officer or configuration input.","status":"unresolved"},
 {"target":"StrategyUsageValue","source":"LTP.Meas/TotCtrRdg","rule":"Direct map; parse as numeric.","status":"confirmed"},
 {"target":"NewStrategyUsageValue","source":"LTP actual usage value (candidate)","rule":"Map only when the actual-value source column is explicitly identified; otherwise leave unresolved.","status":"unresolved"},
 {"target":"StrategyDate","source":"LTP.Component Due Date (O)","rule":"Direct map and normalize to ISO date YYYY-MM-DD.","status":"confirmed"},
 {"target":"NewStrategyDate","source":"AMT.Strategy_Date","rule":"Lookup AMT by normalized SerialNumber and normalize to ISO date YYYY-MM-DD.","status":"confirmed"},
 {"target":"SalesStatusCode","source":"Cross_Reference_Workflow.Sales Status (candidate)","rule":"Map only after the allowed values and metric are confirmed; do not guess.","status":"unresolved"},
 {"target":"ReviewStatusCode","source":None,"rule":"Do not infer; require Forecasting Officer or configuration input.","status":"unresolved"},
 {"target":"PartClassificationCode","source":"Cross_Reference_Workflow.NextPartClassification","rule":"Lookup through the current cross-reference bridge.","status":"confirmed"},
 {"target":"SalesLostReasonCode","source":None,"rule":"Do not infer; require Forecasting Officer or configuration input.","status":"unresolved"},
 {"target":"SalesStatusCommentsNote","source":"Forecasting Officer input","rule":"Populate manually; AI may extract an explicit supplied comment but must not generate one.","status":"confirmed"},
 {"target":"PurchaseOrderNumber","source":None,"rule":"Default to null for forecast records until PO handling is confirmed.","status":"provisional"}
]
artifact = {
 "artifact":"FMG_NEO_schema_mapping_business_rules",
 "version":"1.0.0",
 "scope":{"client":"FMG","input":"LTP","target":"NEO","primary_input_identifier":"Functional Loc"},
 "precedence":["confirmed rule","current source data","current cross-reference bridge","provisional rule","manual review"],
 "normalization":[
  "Trim surrounding whitespace from identifiers and codes.",
  "Preserve identifiers as strings, including leading zeros.",
  "Treat blank strings and whitespace-only cells as null.",
  "Normalize dates to YYYY-MM-DD; reject ambiguous or invalid dates.",
  "Parse numeric measures without formatting characters; do not treat zero as null."
 ],
 "identity":{"record_key":["SerialNumber","ComponentCode","ModifierCode"],"rule":"Serial/equipment number alone is not unique because one machine can have multiple components."},
 "join_rules":[
  {"from":"LTP","to":"AMT","key":"normalized SerialNumber/equipment number","cardinality":"one-to-many possible","action":"Resolve the component row using ComponentCode and ModifierCode; if still non-unique, route to exception."},
  {"from":"customer data","to":"cross-reference","key":"Functional Loc / normalized identifiers","action":"Use only the current cross-reference as a bridge; never backfill from obsolete historical rows."},
  {"from":"mapped row","to":"Snowflake NEO template","key":"SerialNumber + ComponentCode + ModifierCode","action":"Use Snowflake to recreate the current NEO shape and test existence."}
 ],
 "row_rules":[
  {"id":"ROW-001","if":"customer-provided NEO/changeout date is present","then":"use it as the actual NEO date after normalization","status":"confirmed"},
  {"id":"ROW-002","if":"required NEO date is blank or null after approved sourcing","then":"skip the row","status":"confirmed"},
  {"id":"ROW-003","if":"record key does not exist in current Snowflake data","then":"emit the source row to the exception report; do not automatically add it to NEO","status":"confirmed"},
  {"id":"ROW-004","if":"an exception is determined to be a false positive","then":"reclassify only from explicit Forecasting Officer feedback","status":"confirmed"},
  {"id":"ROW-005","if":"multiple AMT or cross-reference candidates remain after key resolution","then":"route to exception and include candidate-count/reason metadata","status":"derived"}
 ],
 "mapping_rules":mappings,
 "ai_guardrails":[
  "Never invent values for unresolved fields.",
  "Never use historical cross-reference data when the record is absent from the latest dataset.",
  "Never collapse distinct component rows sharing the same SerialNumber.",
  "Return confidence and rule status for every mapped field.",
  "For exceptions, retain the full source row and a machine-readable reason code.",
  "Do not implement the annual-hours/frequency fallback calculation unless separately approved."
 ],
 "exception_reason_codes":["MISSING_NEO_DATE","NOT_IN_SNOWFLAKE","AMBIGUOUS_AMT_MATCH","AMBIGUOUS_CROSS_REFERENCE","INVALID_DATE","MISSING_REQUIRED_KEY","UNRESOLVED_REQUIRED_FIELD"],
 "open_questions":["SiteCode source/default","FleetCode source/default","RegistrationCounter rule","SourceOfSupplyCode rule","StrategyUOMCode rule","NewStrategyUsageValue source","SalesStatusCode values and metric","ReviewStatusCode rule","SalesLostReasonCode rule","PurchaseOrderNumber forecast behavior"]
}
json_text = json.dumps(artifact, indent=2, ensure_ascii=False)
json.loads(json_text)
confirmed = sum(x["status"] == "confirmed" for x in mappings)
unresolved = sum(x["status"] == "unresolved" for x in mappings)
provisional = sum(x["status"] == "provisional" for x in mappings)
md_lines = [
 "# FMG NEO AI-Assisted Schema Mapping Business Rules", "",
 "## Scope", "- Client: FMG", "- Input: LTP", "- Target: NEO", "- Primary LTP identifier: `Functional Loc`", "",
 "## Record identity", "Use `SerialNumber + ComponentCode + ModifierCode` as the record key. Serial/equipment number alone is not unique because a machine can have multiple components.", "",
 "## Processing rules",
 "1. Normalize identifiers, dates, nulls, and numeric values before matching.",
 "2. Use current customer data and the current cross-reference bridge; do not backfill from obsolete historical rows.",
 "3. Use Snowflake to recreate the current NEO shape and to test whether the composite key exists.",
 "4. If the required NEO date is blank after approved sourcing, skip the row.",
 "5. If the key is absent from Snowflake or matching is ambiguous, emit the full row to the exception report.",
 "6. Reclassify false-positive exceptions only from explicit Forecasting Officer feedback.",
 "7. Do not implement the annual-hours/frequency fallback unless separately approved.", "",
 "## Field mapping matrix", "| NEO target | Source | Rule | Status |", "|---|---|---|---|"
]
for m in mappings:
    src = ", ".join(m["source"]) if isinstance(m["source"], list) else (m["source"] or "TBD")
    md_lines.append(f"| `{m['target']}` | `{src}` | {m['rule']} | {m['status']} |")
md_lines += ["", "## AI guardrails"] + [f"- {x}" for x in artifact["ai_guardrails"]]
md_lines += ["", "## Exception reason codes"] + [f"- `{x}`" for x in artifact["exception_reason_codes"]]
md_lines += ["", "## Open questions"] + [f"- {x}" for x in artifact["open_questions"]]
md_text = "\n".join(md_lines)
print(f"JSON valid: yes; fields={len(mappings)}; confirmed={confirmed}; provisional={provisional}; unresolved={unresolved}; row_rules={len(artifact['row_rules'])}; markdown_lines={len(md_lines)}")
print("Artifacts prepared: FMG_NEO_business_rules.json and FMG_NEO_business_rules.md")