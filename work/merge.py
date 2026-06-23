#!/usr/bin/env python3
"""
Merge per-batch research results into the final enriched CSV.

- Reads original uploaded CSV.
- Reads all results/batch_*.json (each: list of {idx, n_signals, signals, score}).
- Fills ONLY the Signals (col 13) and Scores (col 14) columns for the
  previously-empty rows (data-index 1000..1385). Everything else untouched.
- Doubles as a progress checker: prints which batches/idx are still missing.
- Writes keycodes_final_enriched.csv only when --write is passed AND all
  386 target rows are covered.
"""
import csv, glob, json, os, sys

ORIG = "/root/.claude/uploads/fc1c6a52-6094-53e7-907a-a7509f22106f/64fddf00-keycodes_final_qualified_leads__keycodes_final_qualified_leads.csv.csv"
RESULTS_DIR = "/home/user/Claude-Code/work/results"
OUT = "/home/user/Claude-Code/keycodes_final_enriched.csv"

VALID_SCORES = {
    "Tier 0: Discard (0-1 Signals) -> Archive / Not Ready",
    "Tier 2: Standard (2 Signals) -> Standard Sequence (No Loom)",
    "Tier 1: High Priority (3+ Signals) -> Full Loom + Multi-Channel",
}
SIG_I, SCORE_I = 13, 14
TARGET_START, TARGET_END = 1000, 1385  # inclusive data-index range to fill

def tier_for(n):
    if n <= 1: return "Tier 0"
    if n == 2: return "Tier 2"
    return "Tier 1"

def load_results():
    recs = {}
    dupes = []
    for fp in sorted(glob.glob(os.path.join(RESULTS_DIR, "batch_*.json"))):
        try:
            arr = json.load(open(fp))
        except Exception as e:
            print(f"  !! {os.path.basename(fp)}: unreadable ({e})")
            continue
        for r in arr:
            idx = r["idx"]
            if idx in recs:
                dupes.append(idx)
            recs[idx] = r
    return recs, dupes

def main():
    write = "--write" in sys.argv
    with open(ORIG, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, data = rows[0], rows[1:]

    recs, dupes = load_results()
    targets = list(range(TARGET_START, TARGET_END + 1))
    have = sorted(i for i in targets if i in recs)
    missing = sorted(i for i in targets if i not in recs)

    print(f"Target rows: {len(targets)} (idx {TARGET_START}-{TARGET_END})")
    print(f"Have results: {len(have)}")
    print(f"Missing: {len(missing)}")
    if dupes:
        print(f"  !! duplicate idx across batches: {sorted(set(dupes))}")

    # batch-level missing summary
    miss_batches = sorted(set((i - TARGET_START)//10 for i in missing))
    if miss_batches:
        print(f"Missing batch numbers: {['batch_%02d'%b for b in miss_batches]}")

    # validate scores / tier consistency
    errs = []
    for i in have:
        r = recs[i]
        s = r.get("score","")
        n = r.get("n_signals", None)
        if s not in VALID_SCORES:
            errs.append(f"idx {i}: invalid score {s!r}")
        if isinstance(n, int) and tier_for(n) not in s:
            errs.append(f"idx {i}: n_signals={n} but score={s!r}")
    if errs:
        print(f"\nVALIDATION ERRORS ({len(errs)}):")
        for e in errs[:30]:
            print("  " + e)

    # tier counts so far
    from collections import Counter
    c = Counter()
    for i in have:
        c[tier_for(recs[i].get("n_signals",0))] += 1
    print(f"\nTier counts (completed): Tier0={c['Tier 0']} Tier2={c['Tier 2']} Tier1={c['Tier 1']}")

    if not write:
        print("\n[dry-run] pass --write to emit CSV (only when 0 missing).")
        return 0
    if missing:
        print(f"\nREFUSING to write: {len(missing)} rows still missing.")
        return 1
    if errs:
        print(f"\nREFUSING to write: {len(errs)} validation errors.")
        return 1

    # apply
    for di, row in enumerate(data):
        if di in recs:
            while len(row) <= SCORE_I:
                row.append("")
            row[SIG_I] = recs[di]["signals"]
            row[SCORE_I] = recs[di]["score"]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(data)
    print(f"\nWROTE {OUT} ({len(data)} data rows)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
