-- Analysis queries over the structural-retrieval study database (see etl.py)
-- Each reproduces a table or finding from the paper (arXiv:2609.01556)

-- 1. Spend reconciliation per provider
SELECT provider, COUNT(*) AS count, ROUND(SUM(cost_usd), 2) AS total_cost, ROUND(AVG(cost_usd), 5) AS avg_cost FROM api_calls GROUP BY provider ORDER BY total_cost DESC;

-- 2. Headline totals
SELECT COUNT(*) AS total_calls, ROUND(SUM(cost_usd),2) AS total_spend FROM api_calls;

-- 3. Cost and volume per model
SELECT model, COUNT(*) AS call_count, ROUND(SUM(cost_usd), 2) AS total_cost, SUM(output_tokens) AS total_output_tokens FROM api_calls GROUP BY model ORDER BY total_cost DESC;

-- 4. Truncation proxy: calls at budget cap
SELECT model, COUNT(*) AS total_calls, SUM(CASE WHEN output_tokens IN (8192, 16384, 65536) THEN 1 ELSE 0 END) AS calls_at_cap, ROUND(100.0 * AVG(CASE WHEN output_tokens IN (8192, 16384, 65536) THEN 1 ELSE 0 END), 1) AS cap_rate_pct FROM api_calls GROUP BY model ORDER BY cap_rate_pct DESC;

-- 5. Baseline strict hits per embedder and tier (paper Table 1)
SELECT embedder, tier, hit1, hit5, hit10 FROM baseline_hits WHERE metric='strict' ORDER BY embedder, tier;

-- 6. Strict vs lenient pivot
SELECT embedder, tier, MAX(CASE WHEN metric='strict' THEN hit1 END) AS strict_hit1, MAX(CASE WHEN metric='lenient' THEN hit1 END) AS lenient_hit1, ROUND(MAX(CASE WHEN metric='lenient' THEN hit1 END) - MAX(CASE WHEN metric='strict' THEN hit1 END), 3) AS gap FROM baseline_hits GROUP BY embedder, tier ORDER BY embedder, tier;

-- 7. Reranker gap-closed by judge, prompt style, tier
SELECT judge, prompt_style, tier, n_unparsed, ROUND(100*share_closed,1) AS pct_gap_closed FROM reranker_runs ORDER BY tier, pct_gap_closed DESC;

-- 8. Best judge per tier (argmax via pair-IN)
WITH judge_scores AS (SELECT judge, tier, share_closed FROM reranker_runs WHERE prompt_style='plain') SELECT judge, tier, ROUND(100*share_closed,1) AS pct_gap_closed FROM judge_scores WHERE (tier, share_closed) IN (SELECT tier, MAX(share_closed) FROM judge_scores GROUP BY tier);

-- 9. Lexical similarity of false positives among misses
SELECT embedder, tier, n_misses, ROUND(pct_fp_more_similar, 1) AS pct_fp_more_similar FROM lexical_misses ORDER BY pct_fp_more_similar DESC;

-- 10. Running cumulative spend per provider (window function)
SELECT ts, provider, cost_usd, ROUND(SUM(cost_usd) OVER (PARTITION BY provider ORDER BY ts), 4) AS running_spend FROM api_calls LIMIT 10;
