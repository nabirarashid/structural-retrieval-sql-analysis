"""ETL: load structural-retrieval study artifacts into SQLite.
Sources: results/ JSONs from github.com/nabirarashid/structural-retrieval
Tables: api_calls, baseline_hits, reranker_runs, lexical_misses
"""
import json, sqlite3, glob, os, sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "../structural-retrieval"
DB = "study.db"
if os.path.exists(DB): os.remove(DB)
con = sqlite3.connect(DB)
c = con.cursor()

c.executescript("""
CREATE TABLE api_calls (
  call_id INTEGER PRIMARY KEY,
  ts REAL, provider TEXT, model TEXT,
  input_tokens INTEGER, output_tokens INTEGER,
  cost_usd REAL, note TEXT
);
CREATE TABLE baseline_hits (
  embedder TEXT, tier TEXT, metric TEXT,
  hit1 REAL, hit5 REAL, hit10 REAL,
  n_queries INTEGER, corpus_size INTEGER
);
CREATE TABLE reranker_runs (
  judge TEXT, prompt_style TEXT, tier TEXT,
  n_queries INTEGER, orig_hit1 REAL, orig_hit10 REAL,
  reranked_hit1 REAL, n_unparsed INTEGER,
  recoverable_gap REAL, gap_closed REAL, share_closed REAL
);
CREATE TABLE lexical_misses (
  embedder TEXT, tier TEXT, n_misses INTEGER,
  gold_sim_mean REAL, fp_sim_mean REAL,
  delta_fp_minus_gold REAL, pct_fp_more_similar REAL
);
""")

# 1) api_calls from SPEND.json
spend = json.load(open(f"{REPO}/results/SPEND.json"))
rows = [(i+1, x["ts"], x["provider"], x["model"], x["input_tokens"],
         x["output_tokens"], x["cost"], x.get("note","")) for i, x in enumerate(spend["calls"])]
c.executemany("INSERT INTO api_calls VALUES (?,?,?,?,?,?,?,?)", rows)

# 2) baseline_hits from baseline_*.json (easy = unsuffixed, hard = _hard)
for f in glob.glob(f"{REPO}/results/baseline_*.json"):
    d = json.load(open(f))
    tier = "hard" if f.endswith("_hard.json") else "easy"
    for metric in ("strict", "lenient"):
        h = d.get(f"{metric}_hit")
        if h:
            c.execute("INSERT INTO baseline_hits VALUES (?,?,?,?,?,?,?,?)",
                (d["provider"], tier, metric, h.get("Hit@1"), h.get("Hit@5"),
                 h.get("Hit@10"), d.get("n_queries"), d.get("corpus_size")))

# 3) reranker_runs from llm_reranker files
def load_rr(path, judge, style):
    d = json.load(open(path))
    rows = d if isinstance(d, list) else d.get("results", [])
    for r in rows:
        c.execute("INSERT INTO reranker_runs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (r.get("judge", judge), style, r["tier"], r["n_queries"],
             r["orig_hit1"], r["orig_hit10"], r["llm_reranked_hit1"],
             r["n_unparsed_responses"], r["recoverable_gap"],
             r["gap_closed"], r["share_of_recoverable_gap_closed"]))

load_rr(f"{REPO}/results/llm_reranker_full.json", "gemini", "plain")
load_rr(f"{REPO}/results/llm_reranker_full_glm.json", "glm", "plain")
load_rr(f"{REPO}/results/llm_reranker_full_cot_gemini.json", "gemini", "cot")
load_rr(f"{REPO}/results/llm_reranker_full_cot_glm.json", "glm", "cot")

# 4) lexical_misses
for r in json.load(open(f"{REPO}/results/lexical_distance_check.json")):
    c.execute("INSERT INTO lexical_misses VALUES (?,?,?,?,?,?,?)",
        (r["provider"], r["tier"], r["n_misses"],
         r["anchor_to_gold"]["mean"], r["anchor_to_false_positive"]["mean"],
         r["delta_fp_minus_gold"] if isinstance(r["delta_fp_minus_gold"], float) else r["delta_fp_minus_gold"].get("mean"),
         r["pct_misses_where_fp_more_lexically_similar_than_gold"]))

con.commit()
for t in ["api_calls","baseline_hits","reranker_runs","lexical_misses"]:
    print(t, c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
print("total spend:", round(c.execute("SELECT SUM(cost_usd) FROM api_calls").fetchone()[0], 2))
