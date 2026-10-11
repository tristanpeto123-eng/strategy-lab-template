# Historical supply evidence (required for evidence-backed testing)

This CSV starts with **zero verified events** deliberately.

Add original, date-verifiable primary sources (SEC company disclosures, earnings transcripts with dates, government releases, port/shipping data, exchange announcements, memory-contract price publications). Do not mark opinion articles as verified.

Required columns: `event_id`, `theme`, `ticker`, `source_url`, `source_published_at`, `publicly_available_at`, `verified`, `evidence_type`, `details`.

Use ISO date `YYYY-MM-DD`; for conservative backtesting, `publicly_available_at` is the first date by which you can demonstrate the event was publicly accessible. It must not be earlier than `source_published_at`. For ambiguous publication time, trade strictly **after** the next completed day. `verified=true` only after independent source validation.

`event_id` must identify a **real independent episode**, not each repeating headline. Avoid repeat rows within the same event. The same historic ticker chosen today introduces survivorship bias and should not be read as an exhaustive historic universe.

Importing today's 300+ Supply Scout headlines and assigning their old newspaper publication dates would be a severe **retroactive timing error**. Evidence collected after the historical date may be used for archival case reconstruction only with clear point-in-time source provenance. Keep case reconstruction separate from real-time discovery claims.

No shortage-event model will train unless 80+ independently verified events with mature 90-day outcomes and enough winners/losers/sector variation exist. The browser can always test **technical-only** rules using downloaded historical prices.
