# Applicable Query Types — Europe Real Estate Dataset

**Tables:** `properties` (200 rows) · `city_centers` (5 rows)

---

## Level 1 — Retrieval

| # | Query Type | Example |
|---|---|---|
| 1 | **Lookup** | Get property by `id` |
| 2 | **Existence** | Does property 123 exist? |
| 3 | **Count** | How many properties are listed? |

---

## Level 2 — Listing

| # | Query Type | Example |
|---|---|---|
| 4 | **List** | List all properties |
| 5 | **Paginated** | Show page 3 of properties |
| 6 | **Sorted** | Cheapest properties first (by `price`, `size_sqm`, `distance_from_city_km`) |

---

## Level 3 — Filtering

| # | Query Type | Example |
|---|---|---|
| 7 | **Single Filter** | Properties in Paris / intent = `rent` / type = `apartment` |
| 8 | **Multi-Filter** | Berlin + 3 bedrooms + under €300k |
| 9 | **Range** | `price` between €200k–€500k, `size_sqm` between 30–60 |
| 10 | **Set Membership** | Properties in London, Paris, or Berlin |
| 11 | **Pattern Match** | `title` or `description` contains "garden" |

---

## Level 4 — Aggregation

| # | Query Type | Example |
|---|---|---|
| 12 | **Sum** | Total value of all listings |
| 13 | **Average** | Average `price` or `size_sqm` |
| 14 | **Min/Max** | Most / least expensive property |
| 15 | **Grouping** | Average price by `city`, `property_type`, or `bedrooms` |
| 16 | **Distinct** | List unique cities, neighbourhoods, property types |

---

## Level 5 — Relationship

| # | Query Type | Example |
|---|---|---|
| 17 | **Join** | `properties JOIN city_centers ON city` — enriches each property with lat/lon |

---

## Level 6 — Analytical

| # | Query Type | Example |
|---|---|---|
| 20 | **Comparison** | London vs Paris average prices; rent vs buy distribution |
| 22 | **Distribution** | Bedroom count distribution; property type split by city |
| 23 | **Ranking** | Top 10 most expensive cities / neighbourhoods |
| 24 | **Percentile** | Top 5% most expensive properties |
| 25 | **Window** | Rank properties within each city by price |

---

## Level 8 — Geospatial

| # | Query Type | Example |
|---|---|---|
| 29 | **Radius** | Properties within 10 km of city center (via `distance_from_city_km` or joined lat/lon) |
| 30 | **Nearest Neighbor** | Property closest to a given city center |

---

## Level 9 — Search

| # | Query Type | Example |
|---|---|---|
| 33 | **Full Text Search** | Search `title` and `description` for "garden", "modern", "spacious" |

---

## Level 11 — AI / Agent

| # | Query Type | Example |
|---|---|---|
| 39 | **NL2SQL** | "Show me 3-bedroom rentals under €1500 in Berlin" → LLM generates SQL |

---

## Not Applicable (reasons)

| # | Query Type | Reason |
|---|---|---|
| 21 | Trend | No date/time column in dataset |
| 26–28 | Similarity / Recommendation / Collaborative | No user behaviour or embeddings |
| 31–32 | Polygon / Route | No boundary geometries or commute data |
| 36–38 | Graph | No graph relationships |
| 18 | Parent-Child (Amenities) | Excluded per scope |
| 40–43 | Agentic / RAG | Excluded per scope |
