# KIPRIS Plus patent review MVP

This command-line MVP collects real records from the KIPRIS Plus free-search API and ranks them to help a person choose what to review first. It does not generate patent records or make legal conclusions.

## Separate collection and evaluation inputs

The positional argument is sent to KIPRIS as the broad API search term. `--technology` is used only for relevance evaluation.

```powershell
$env:KIPRIS_API_KEY = "YOUR_API_KEY"
python main.py "battery" --technology "electric vehicle battery cooling" --debug
```

## Concept groups and matching

The default groups in `main.py` are:

- `vehicle`: Korean aliases for electric vehicle, vehicle, and automobile
- `battery`: Korean alias for battery
- `cooling`: Korean aliases for cooling, thermal/temperature management, water cooling, coolant, refrigerant, and heat exchange

Only the configured phrases are matched literally. No fuzzy or partial-character similarity is used; for example, the Korean word for "cold forging" does not match the distinct configured word for "cooling". Only concept groups present in `--technology` are evaluated.

## Explainable score

Points are added for concept evidence. A title match is worth more than the same concept in the abstract.

| Evidence | Points |
| --- | ---: |
| Title: vehicle / battery / cooling | 3 / 4 / 6 |
| Abstract: vehicle / battery / cooling | 2 / 2 / 3 |
| Battery and cooling both present | +65 |
| Only one of battery or cooling present | +25 |
| Vehicle concept present | +5 |
| IPC family H01M / B60L | +2 each |

Scores are capped at 100. The thresholds near the top of `main.py` are easy to change: high at 70 or above, medium at 40 to below 70, and low below 40. Finding both battery and cooling in the title/abstract evidence reaches the high band; vehicle evidence adds points. IPC is not searched for Korean keywords. H01M is a small supplement when battery is evaluated, and B60L is a small supplement when vehicle is evaluated.

The CSV includes `relevance_score`, `review_priority`, `matched_concepts`, and `score_reason`. `matched_concepts` lists the concept IDs and applicable IPC codes. `score_reason` gives a short explanation. `applicationNumber` stays a string identifier. Records are sorted by score descending; ties keep the KIPRIS response order.

This score is only a human review aid. It does not assess legal similarity, prior-art status, patentability, or infringement. For a future Streamlit UI, `collect_kipris_data`, `calculate_relevance`, and `classify_priority` are reusable functions.

If the evaluation phrase matches none of the configured concept groups, `main.py` falls back to literal keywords extracted from that phrase. It drops short/common terms and common Korean particles/endings, gives title matches more weight than abstract matches, adds a small bonus when multiple keywords occur, and keeps H01M/B60L as small supplementary IPC signals. This fallback is marked with `analysis_mode=generic_keyword`; the Streamlit UI displays a notice when it is active.

## Debugging

`--debug` prints HTTP status, KIPRIS result fields, a response preview, record counts, and the first record's field names. The API key is redacted and never printed.
