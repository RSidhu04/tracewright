import math
from collections import defaultdict


def compare(baseline, candidate, tolerance=0.0, alpha=0.05):
    if not 0 <= tolerance <= 1 or not 0 < alpha < 1:
        raise ValueError("invalid tolerance or alpha")
    for field in ("suite_hash", "repeats", "seed"):
        if baseline[field] != candidate[field]:
            raise ValueError(f"incompatible runs: {field}")
    def indexed(run):
        rows = {(r["case_id"], r["trial"], r["seed"]): r for r in run["results"]}
        if len(rows) != len(run["results"]) or not rows:
            raise ValueError("empty or duplicate results")
        return rows
    left, right = indexed(baseline), indexed(candidate)
    if left.keys() != right.keys():
        raise ValueError("incompatible result pairs")
    grouped = defaultdict(list)
    for key, row in left.items():
        grouped[key[0]].append(int(right[key]["passed"]) - int(row["passed"]))
    cases = [{"case_id": key, "delta": sum(values)/len(values)} for key, values in sorted(grouped.items())]
    delta = sum(c["delta"] for c in cases)/len(cases)
    # One bounded [-1, 1] observation per case; repeats are NOT extra cases.
    radius = math.sqrt(2 * math.log(2/alpha) / len(cases))
    interval = [max(-1.0, delta-radius), min(1.0, delta+radius)]
    status = "regression" if interval[1] < -tolerance else (
        "noninferior" if interval[0] >= -tolerance else "inconclusive")
    return {"baseline_id": baseline["id"], "candidate_id": candidate["id"],
            "baseline_pass_rate": sum(r["passed"] for r in left.values())/len(left),
            "candidate_pass_rate": sum(r["passed"] for r in right.values())/len(right),
            "delta": delta, "case_count": len(cases), "paired_trials": len(left),
            "case_deltas": cases, "observed_regressions": [c["case_id"] for c in cases if c["delta"] < -tolerance],
            "statistical_status": status, "interval": interval, "alpha": alpha,
            "tolerance": tolerance, "method": "case-level Hoeffding bounded-mean interval",
            "caveat": "Coverage requires independent representative cases. Curated/correlated suites do not establish population reliability. Repeats do not increase case sample size. No per-case significance claims; no multiple-comparison correction. Preselect one comparison and alpha."}
