# Output Schema Reference

Each scraped record conforms to `data/schema.json` (JSON Schema Draft 7).

## Required Fields

| Field | Type | Description |
|---|---|---|
| `company_name` | string | Full company name as on Screener.in |
| `ticker` | string | NSE/BSE ticker symbol (e.g. `"INFY"`) |
| `exchange` | string | `"NSE"` or `"BSE"` |
| `cmp` | number | Current market price (INR) |
| `dividend_yield_pct` | number | Dividend yield as a percentage (e.g. `3.5` for 3.5%) |
| `scraped_at` | string | ISO 8601 UTC timestamp |
| `source_url` | string | Full URL of the scraped screen |

## Optional Fields

| Field | Type | Description |
|---|---|---|
| `pe_ratio` | number \| null | Price-to-earnings ratio |
| `market_cap_cr` | number \| null | Market cap in crores INR |
| `roce_pct` | number \| null | Return on capital employed (%) |
| `roe_pct` | number \| null | Return on equity (%) |
| `sales_growth_pct` | number \| null | Sales growth (%) |

## Dataset Envelope (`data/latest.json`)

```json
{
  "meta": {
    "scraped_at": "2024-06-15T10:30:00Z",
    "source_url": "https://www.screener.in/screens/...",
    "collector_id": "c_msvhzc3s2gixuk6k42",
    "record_count": 25
  },
  "records": [ /* array of canonical records */ ]
}
```

## Diff Engine Thresholds

| Threshold | Default | Meaning |
|---|---|---|
| `yield_change_pp` | `0.5` | Minimum yield change (percentage points) to flag as CHANGED |

Classifications: `ENTERED` (new ticker), `EXITED` (ticker dropped off screen), `CHANGED` (yield moved past threshold), `UNCHANGED`.
