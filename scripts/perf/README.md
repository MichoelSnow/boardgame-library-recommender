# Performance Scripts

## `benchmark_recommendation_size.py`
- What it does:
  - Benchmarks recommendation latency versus liked-game list size.
- When to use:
  - Recommendation performance analysis and regression checks.
- How to use:
```bash
poetry run python scripts/perf/benchmark_recommendation_size.py \
  --env dev \
  --game-ids "224517,167791,174430,173346,266192" \
  --sizes "1,5,10,20,35,50" \
  --iterations 20 \
  --limit 5 \
  --pax-only true
```
