"""Mapping engine — orchestrates the established workflow end to end.

Order (unchanged from the project):
  detect sheets -> profile columns -> deterministic score -> LLM refine (optional)
  -> normalize/quarantine rows -> build NEO/LAO -> assemble mapping_report.
"""
from __future__ import annotations
import pandas as pd

from . import profiling, scorer, builders, normalizer
from .llm_mapper import refine_mapping
from .settings import settings, detect_prompt_variant

# Content-rescue thresholds for sheet selection (see _content_score / run_mapping).
# A sheet whose name matches no configured pattern for a role can still be picked, but
# only if it plausibly fits (MIN) and clearly beats whatever name-matching found
# (MARGIN) — this avoids a coincidentally-similar, unrelated sheet stealing a role.
_RESCUE_MIN_SCORE = 0.60
_RESCUE_MARGIN = 0.10


def _content_score(frames: dict, sheet: str, fields: list[dict], scoring: dict) -> float:
    """Mean deterministic confidence this sheet's columns would get against `fields` —
    i.e. how well this sheet's content (not its name) fits a target's canonical fields.
    """
    df = frames[sheet]
    if df.empty:
        return -1.0
    profiles = profiling.profile_columns(df)
    det = scorer.score_target(fields, profiles, scoring)
    vals = [d["confidence"] for d in det.values()]
    return sum(vals) / len(vals) if vals else 0.0


def _pick_sheet(frames: dict, candidates: list[str], fields: list[dict], scoring: dict) -> str:
    """Tie-break multiple matching tabs by how well their columns actually score
    against the target's canonical fields (reusing the deterministic scorer) — NOT by
    row count. A large raw extract (e.g. a "PARTS" transaction log, or a sheet that
    happens to be literally named "LTP" but is raw SAP data) can dwarf a smaller,
    already-clean/pre-mapped sheet in row count while scoring far worse on content.
    """
    if len(candidates) == 1:
        return candidates[0]
    return max(candidates, key=lambda s: _content_score(frames, s, fields, scoring))


def run_mapping(workbook_path: str, cfg: dict) -> dict:
    prompt_variant = detect_prompt_variant(workbook_path)
    frames = profiling.read_workbook(workbook_path)
    sheet_match = profiling.match_sheets(list(frames.keys()), cfg["sheet_config"])
    role_target = {e["role"]: e["target"] for e in cfg["sheet_config"]}

    # Resolve role -> concrete sheet name. Two passes:
    #   1. Among name-pattern-matched candidates, pick the best-scoring one (as before).
    #   2. Content-rescue: scan every OTHER, not-yet-claimed sheet in the workbook in
    #      case the true source sheet's name matches no configured pattern at all (a
    #      sheet named after the customer, e.g., rather than "LTP"/"parts"/etc.) — only
    #      swap in a rescued sheet when it clearly, decisively fits better.
    role_to_sheet, warnings, claimed = {}, [], set()

    for role, info in sheet_match["matched"].items():
        target_fields = cfg["targets"].get(info["target"], {}).get("fields", [])
        scoring = cfg["scoring"]
        candidates = [s for s in info["candidates"] if s not in claimed] or info["candidates"]
        name_pick = _pick_sheet(frames, candidates, target_fields, scoring)
        name_score = _content_score(frames, name_pick, target_fields, scoring)

        rescue_pool = [s for s in frames if s not in claimed and s not in info["candidates"]]
        best_rescue, best_rescue_score = None, -1.0
        for s in rescue_pool:
            sc = _content_score(frames, s, target_fields, scoring)
            if sc > best_rescue_score:
                best_rescue, best_rescue_score = s, sc

        if (
            best_rescue is not None
            and best_rescue_score >= _RESCUE_MIN_SCORE
            and best_rescue_score >= name_score + _RESCUE_MARGIN
        ):
            chosen = best_rescue
            warnings.append(
                f"Role {role}: '{chosen}' (content score {best_rescue_score:.2f}) fits "
                f"better than name-matched {info['candidates']} (best {name_score:.2f}); "
                f"its name matches no configured pattern — consider adding one."
            )
        else:
            chosen = name_pick
            if len(info["candidates"]) > 1:
                warnings.append(
                    f"Role {role} matched {info['candidates']}; picked '{chosen}' by content score."
                )

        role_to_sheet[role] = chosen
        claimed.add(chosen)

    # Roles no configured pattern matched at all get one more chance: the best-scoring
    # unclaimed sheet in the workbook, if it plausibly fits.
    still_unmatched = []
    for role in sheet_match["unmatched_roles"]:
        target_fields = cfg["targets"].get(role_target.get(role), {}).get("fields", [])
        scoring = cfg["scoring"]
        pool = [s for s in frames if s not in claimed]
        best, best_score = None, -1.0
        for s in pool:
            sc = _content_score(frames, s, target_fields, scoring)
            if sc > best_score:
                best, best_score = s, sc
        if best is not None and best_score >= _RESCUE_MIN_SCORE:
            role_to_sheet[role] = best
            claimed.add(best)
            warnings.append(
                f"Role {role} matched no configured sheet-name pattern; content-score "
                f"rescued '{best}' ({best_score:.2f}) — consider adding a name pattern."
            )
        else:
            still_unmatched.append(role)

    # Measurement-Points functional-location values for the LTP join-key bonus
    # mp_role = "MEASUREMENT_POINTS"
    mp_role = cfg["normalization"].get("join_key_role", "MEASUREMENT_POINTS")
    mp_key_values = set()
    if mp_role in role_to_sheet:
        mp_df = frames[role_to_sheet[mp_role]]
        for col in mp_df.columns:
            if "functional" in str(col).lower() or "function location" in str(col).lower():
                mp_key_values = set(mp_df[col].dropna().astype(str))
                break

    report = {
        "matched_sheets": [
            {"role": r, "sheet_name": s, "rows": int(len(frames[s]))}
            for r, s in role_to_sheet.items()
        ],
        "unmatched_roles": still_unmatched,
        "mappings": {},
        "column_confidence_summary": {},
        "row_counts": {},
        "warnings": warnings,
        "llm_used": settings.llm_configured(),
        "prompt_variant": prompt_variant or "main",
    }

    outputs = {}          # target -> DataFrame
    rejected_frames = []  # Normalized rows across sheets

    for target, tcfg in cfg["targets"].items():
        role = tcfg["source_sheet_role"]
        if role not in role_to_sheet:
            report["mappings"][target] = []
            continue
        df = frames[role_to_sheet[role]]
        profiles = profiling.profile_columns(df)

        # join-overlap function for the join key
        def _overlap(colname, _df=df):
            vals = set(_df[colname].dropna().astype(str))
            if not vals or not mp_key_values:
                return 0.0
            return len(vals & mp_key_values) / len(vals)

        det = scorer.score_target(tcfg["fields"], profiles, cfg["scoring"], _overlap)

        # LLM refinement (alias reasoning + notes); deterministic numbers stand unless LLM
        # picks a *different valid* column, in which case we keep the deterministic score
        # for that column but record the LLM note.
        llm = refine_mapping(target, tcfg["fields"], profiles, det, prompt_variant=prompt_variant)

        resolved, rows = {}, []
        auto_accept_bar = cfg["scoring"].get("bands", {}).get("auto_accept", 0.9)
        for f in tcfg["fields"]:
            can = f["canonical"]
            sc = f.get("source_class")
            if sc == "customer_file":
                d = det.get(can, {})
                src = d.get("source_column")
                conf = d.get("confidence", 0.0)
                band = d.get("band", "reject")
                note = ""
                llm_d = llm.get(can)
                llm_col = llm_d.get("source_column") if llm_d else None

                if conf < auto_accept_bar and llm_d and llm_col:
                    # Deterministic ruling didn't clear auto_accept: skip it for this
                    # field and let the model's own column choice + calibrated
                    # confidence stand instead of the arithmetic score. See
                    # prompts/README.md ("Model-authoritative mapping below auto_accept").
                    src = llm_col
                    conf = round(float(llm_d.get("confidence", conf)), 3)
                    band = scorer.band_for(conf, cfg["scoring"].get("bands", {}))
                    note = (
                        f"Model-decided (deterministic {d.get('confidence', 0.0):.2f} "
                        f"< {auto_accept_bar:.2f}): {llm_d.get('notes', '')}"
                    )
                elif llm_d and llm_col and llm_col != src:
                    # Deterministic pick already cleared auto_accept; the LLM may still
                    # correct the column for review, but its computed score stands.
                    src = llm_col
                    note = f"LLM override: {llm_d.get('notes', '')}"
                elif llm_d:
                    note = llm_d.get("notes", "")

                resolved[can] = src
                rows.append({
                    "canonical_field": can, "source_column": src, "source_class": sc,
                    "name_score": d.get("name_score", 0.0), "value_score": d.get("value_score", 0.0),
                    "confidence": conf, "band": band,
                    "status": "mapped" if src else "unmapped", "notes": note,
                })
            elif sc == "constant":
                rows.append({"canonical_field": can, "source_column": None, "source_class": sc,
                             "confidence": 1.0, "band": "auto_accept", "status": "constant", "notes": ""})
            elif sc == "derived":
                rows.append({"canonical_field": can, "source_column": None, "source_class": sc,
                             "confidence": None, "band": None, "status": "derived",
                             "notes": f"transform={f.get('transform')}"})
            else:  # enrichment
                rows.append({"canonical_field": can, "source_column": None, "source_class": sc,
                             "confidence": 0.0, "band": None, "status": "requires_enrichment",
                             "notes": f"join={f.get('join')}"})
        report["mappings"][target] = rows

        # The summary mean is scoped to fields actually written to <target>.csv
        # (output_columns) — not every customer_file field. Some customer_file fields
        # (e.g. FunctionalLoc, MeasTotCtr) exist only as internal join-key/derived-input
        # plumbing and are never in output_columns; including them would understate the
        # quality of what customers actually receive. They stay fully visible in
        # `mappings` and are reported separately here, never hidden.
        output_cols = set(tcfg.get("output_columns", []))
        customer_rows = [r for r in rows if r["source_class"] == "customer_file" and r["confidence"] is not None]
        deliverable_vals = [r["confidence"] for r in customer_rows if r["canonical_field"] in output_cols]
        support_rows = [r for r in customer_rows if r["canonical_field"] not in output_cols]

        report["column_confidence_summary"][f"{target}_mean"] = (
            round(sum(deliverable_vals) / len(deliverable_vals), 3) if deliverable_vals else None
        )
        if support_rows:
            report["column_confidence_summary"][f"{target}_support_fields"] = [
                {"canonical_field": r["canonical_field"], "confidence": r["confidence"]}
                for r in support_rows
            ]

        # normalize/quarantine
        key_field = cfg["normalization"]["join_key_canonical"]
        key_col = resolved.get(key_field)
        id_field = tcfg.get("identity_canonical")
        id_col = resolved.get(id_field, key_col)
        clean, rejected = normalizer.split_clean_rejected(
            df, role_to_sheet[role], key_col, id_col, cfg["normalization"]["reject_rules"]
        )
        if not rejected.empty:
            rejected_frames.append(rejected)

        outputs[target] = builders.build_target(clean, tcfg, resolved, cfg["constants"])
        report["row_counts"][target] = int(len(outputs[target]))

    normalized = (
        pd.concat(rejected_frames, ignore_index=True) if rejected_frames else pd.DataFrame()
    )
    report["row_counts"]["Normalized"] = int(len(normalized))

    return {"report": report, "outputs": outputs, "normalized": normalized}
