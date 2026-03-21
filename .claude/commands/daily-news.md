Search the web for the TOP 10 most globally important news stories from the LAST 24 HOURS. Use your web search tool to find real, current stories across multiple searches.

For each story collect exactly these fields:
- "rank": integer 1-10 (1 = most important)
- "headline": string, max 12 words
- "summary": string, 2-3 sentences on what happened and why it matters
- "category": one of exactly: Politics, Tech, Finance, Science, Environment, Health, War & Conflict, Business, Society, Other
- "source": news outlet name
- "importance_score": integer 1-10
- "region": e.g. Global, United States, Europe, Asia, Middle East

Once you have all 10 stories, do the following steps in order:

1. Write the JSON array to `/tmp/digest_stories.json` using the Write tool.

2. Run the renderer:
```bash
python3 /Users/dhruvish/Claude/news_digest/digest.py --from-file /tmp/digest_stories.json
```

3. Commit and deploy:
```bash
cd /Users/dhruvish/Claude/news_digest && git add output/digest.html && git commit -m "chore: daily digest $(date +%Y-%m-%d)" && git push
```

The Vercel site will auto-update once pushed. Confirm the push succeeded and share the Vercel URL.
