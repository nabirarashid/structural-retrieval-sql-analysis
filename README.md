# SQL analysis of the structural-retrieval study

This folder rebuilds the evaluation analysis of [*Retrieved but not ranked*](https://arxiv.org/abs/2609.01556) as a SQLite database plus analysis queries. The ETL loads the study's raw result artifacts (the 4,338-row API call ledger, baseline hit metrics, LLM reranker runs, and lexical-distance checks) into four tables; the queries then reproduce the paper's core tables and findings directly from that data.

## Setup
```
python3 etl.py path/to/structural-retrieval
```
Produces `study.db` with tables `api_calls` (4,338 rows), `baseline_hits` (12), `reranker_runs` (16), `lexical_misses` (4).

## Queries and results

### 1. Spend reconciliation per provider
```sql
SELECT provider, COUNT(*) AS count, ROUND(SUM(cost_usd), 2) AS total_cost, ROUND(AVG(cost_usd), 5) AS avg_cost FROM api_calls GROUP BY provider ORDER BY total_cost DESC;
```
```
provider  count  total_cost  avg_cost
--------  -----  ----------  --------
claude    2365   5.3         0.00224 
deepseek  681    3.49        0.00513 
gemini    1292   1.8         0.00139
```
Claude and DeepSeek reconcile exactly with SPEND.json's authoritative provider totals ($5.30, $3.49). Gemini's itemized rows sum to $1.80 vs the authoritative $8.45: per the ledger's own reconstruction note, most Gemini volume (118,108 embedding items, 3,100 flash-lite reranker calls, 625 grader calls) was billed at aggregate level and never itemized as per-call rows.

### 2. Headline totals
```sql
SELECT COUNT(*) AS total_calls, ROUND(SUM(cost_usd),2) AS total_spend FROM api_calls;
```
```
total_calls  total_spend
-----------  -----------
4338         10.59
```
4,338 logged calls, $10.59 itemized. Total study spend including aggregate-billed embedding volume: $17.24.

### 3. Cost and volume per model
```sql
SELECT model, COUNT(*) AS call_count, ROUND(SUM(cost_usd), 2) AS total_cost, SUM(output_tokens) AS total_output_tokens FROM api_calls GROUP BY model ORDER BY total_cost DESC;
```
```
model                  call_count  total_cost  total_output_tokens
---------------------  ----------  ----------  -------------------
claude-haiku-4-5       2365        5.3         11880              
deepseek-v4-flash      681         3.49        12372773           
gemini-3.1-flash-lite  1289        1.78        1316               
gemini-embedding-001   3           0.02        0
```
The solver (deepseek-v4-flash) generated 12.37M output tokens across 681 calls; the judge (claude-haiku-4-5) made 2,365 calls producing only 11,880 tokens. Reasoning is expensive, verdicts are cheap. claude-haiku-4-5's 2,365 ledger calls comprise the paper's 2,354-call reranker run plus the documented 10-call pilot and one probe.

### 4. Truncation proxy: calls at budget cap
```sql
SELECT model, COUNT(*) AS total_calls, SUM(CASE WHEN output_tokens IN (8192, 16384, 65536) THEN 1 ELSE 0 END) AS calls_at_cap, ROUND(100.0 * AVG(CASE WHEN output_tokens IN (8192, 16384, 65536) THEN 1 ELSE 0 END), 1) AS cap_rate_pct FROM api_calls GROUP BY model ORDER BY cap_rate_pct DESC;
```
```
model                  total_calls  calls_at_cap  cap_rate_pct
---------------------  -----------  ------------  ------------
deepseek-v4-flash      681          7             1.0         
gemini-embedding-001   3            0             0.0         
gemini-3.1-flash-lite  1289         0             0.0         
claude-haiku-4-5       2365         0             0.0
```
Only 7 itemized calls (all deepseek) sit exactly at a round token budget. The paper's documented 63.3% CoT truncation occurred in GLM reranker runs, which were cached outside this itemized ledger; their integrity fingerprint appears instead as the n_unparsed counts in query 7.

### 5. Baseline strict hits per embedder and tier (paper Table 1)
```sql
SELECT embedder, tier, hit1, hit5, hit10 FROM baseline_hits WHERE metric='strict' ORDER BY embedder, tier;
```
```
embedder   tier  hit1   hit5   hit10
---------  ----  -----  -----  -----
deepinfra  easy  0.086  0.868  0.952
deepinfra  hard  0.0    0.028  0.21 
gemini     easy  0.122  0.898  0.976
gemini     hard  0.0    0.1    0.554
labembed   easy  0.086  0.878  0.954
labembed   hard  0.0    0.026  0.178
```
Strict Hit@1 is 0.0 on the hard tier for every embedder, while easy tier reaches 8.6-12.2%. This is the paper's headline: retrieval collapses under adversarial disguise. labembed is the lab-hosted second serving of Qwen3-Embedding-8B from the paper's deployment-divergence comparison (Section 4), not a third model.

### 6. Strict vs lenient pivot
```sql
SELECT embedder, tier, MAX(CASE WHEN metric='strict' THEN hit1 END) AS strict_hit1, MAX(CASE WHEN metric='lenient' THEN hit1 END) AS lenient_hit1, ROUND(MAX(CASE WHEN metric='lenient' THEN hit1 END) - MAX(CASE WHEN metric='strict' THEN hit1 END), 3) AS gap FROM baseline_hits GROUP BY embedder, tier ORDER BY embedder, tier;
```
```
embedder   tier  strict_hit1  lenient_hit1  gap  
---------  ----  -----------  ------------  -----
deepinfra  easy  0.086        0.1           0.014
deepinfra  hard  0.0          0.1           0.1  
gemini     easy  0.122        0.148         0.026
gemini     hard  0.0          0.148         0.148
labembed   easy  0.086        0.102         0.016
labembed   hard  0.0          0.102         0.102
```
On the hard tier the entire lenient score is the gap: all surviving credit is surface-form credit.

### 7. Reranker gap-closed by judge, prompt style, tier
```sql
SELECT judge, prompt_style, tier, n_unparsed, ROUND(100*share_closed,1) AS pct_gap_closed FROM reranker_runs ORDER BY tier, pct_gap_closed DESC;
```
```
judge                  prompt_style  tier  n_unparsed  pct_gap_closed
---------------------  ------------  ----  ----------  --------------
gemini-3.1-flash-lite  cot           easy  0           55.4          
gemini-3.1-flash-lite  cot           easy  0           44.7          
gemini                 plain         easy  0           35.6          
gemini                 plain         easy  0           20.6          
glm-5.2-fp8            cot           easy  0           14.3          
glm                    plain         easy  1           12.0          
glm                    plain         easy  1           10.1          
glm-5.2-fp8            cot           easy  2           6.3           
gemini                 plain         hard  0           44.4          
gemini                 plain         hard  0           41.0          
gemini-3.1-flash-lite  cot           hard  0           26.7          
gemini-3.1-flash-lite  cot           hard  0           22.7          
glm-5.2-fp8            cot           hard  3           21.9          
glm                    plain         hard  0           18.1          
glm-5.2-fp8            cot           hard  2           16.6          
glm                    plain         hard  0           10.5
```
Share of recoverable gap closed spans 6.3% to 55.4% within a single tier depending on judge and prompt: direction replicates, magnitudes do not. GLM is the only judge with unparsed responses.

### 8. Best judge per tier (argmax via pair-IN)
```sql
WITH judge_scores AS (SELECT judge, tier, share_closed FROM reranker_runs WHERE prompt_style='plain') SELECT judge, tier, ROUND(100*share_closed,1) AS pct_gap_closed FROM judge_scores WHERE (tier, share_closed) IN (SELECT tier, MAX(share_closed) FROM judge_scores GROUP BY tier);
```
```
judge   tier  pct_gap_closed
------  ----  --------------
gemini  hard  44.4          
gemini  easy  35.6
```
Gemini is the strongest plain-prompt judge on both tiers, the observation that motivated the paper's judge-provenance contamination check.

### 9. Lexical similarity of false positives among misses
```sql
SELECT embedder, tier, n_misses, ROUND(pct_fp_more_similar, 1) AS pct_fp_more_similar FROM lexical_misses ORDER BY pct_fp_more_similar DESC;
```
```
embedder   tier  n_misses  pct_fp_more_similar
---------  ----  --------  -------------------
gemini     hard  500       99.8               
deepinfra  hard  500       99.4               
gemini     easy  439       95.7               
deepinfra  easy  457       95.2
```
In 95.2-99.8% of misses, the winning item is more lexically similar to the query than the gold item: the failure mode is surface form beating structure.

### 10. Running cumulative spend per provider (window function)
```sql
SELECT ts, provider, cost_usd, ROUND(SUM(cost_usd) OVER (PARTITION BY provider ORDER BY ts), 4) AS running_spend FROM api_calls LIMIT 10;
```
```
ts                  provider  cost_usd               running_spend
------------------  --------  ---------------------  -------------
1786989111.684963   claude    0.001075               0.0011       
1786989112.5006132  claude    0.00156                0.0026       
1786989113.5254369  claude    0.0016970000000000002  0.0043       
1786989114.3721092  claude    0.0009860000000000001  0.0053       
1786989115.166194   claude    0.002283               0.0076       
1786989116.189389   claude    0.001031               0.0086       
1786989117.02244    claude    0.0011070000000000001  0.0097       
1786989118.028626   claude    0.000877               0.0106       
1786989118.8510988  claude    0.001244               0.0119       
1786989119.684172   claude    0.002071               0.0139       
...
```
Cost accumulation call-by-call across the study; output truncated to 10 rows here, query returns all 4,338.

## Honesty notes
- The itemized ledger undersums total spend by design; provider-level totals in SPEND.json are authoritative ($17.24). Query 1 documents the reconciliation.
- Truncation analysis (query 4) covers only itemized calls; the 63.3% GLM CoT truncation documented in the paper lives in result files outside this ledger.
- All queries are read-only over published artifacts from the public repo.
