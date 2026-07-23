# Casas do Rio Verde — pricing tool: what shipped & what's next

## Shipped in this change: canonical zones ("ARU zones")

The `region` field used to be free text with only a loose N/S/E/W sort. It's
now a proper, validated **zone system** for Madeira:

- **`competitor_pricing/zones.py`** — single source of truth. Five canonical
  zones (South-West, South / Funchal, South-East, North, Porto Santo), each
  with a stable label, compass bearing, west→east sort order, member towns,
  and a rich alias list. `resolve_zone()` normalises any spelling (compass
  code, zone name, or bare town), ignoring case and accents, and flags
  anything it can't place as **Other / unmapped**.
- **Home-zone awareness** — `us.zone` in the config marks which zone we're in
  (Ponta do Sol → South-West). The dashboard highlights it, because the most
  meaningful comparison is against competitors in *our own* area.
- **Dashboard compass** — the zone cards now show, per zone: average price,
  cheapest entry, property count, and % vs. us; they render in canonical
  west→east order; the home zone gets a `home` badge and the cheapest zone
  gets a `cheapest` badge.
- **Validation & tests** — unmapped regions are logged as warnings at config
  load; `tests/test_zones.py` covers normalisation, partial matching, accents,
  ordering, and the tricky "short token" false-match cases.

---

## Suggested next improvements (roughly prioritised)

### 1. Per-zone alerts & a "home-zone leaderboard" (high value, small)
Today alerts are global (price move ≥10%, undercut, sold out). Add zone-scoped
signals that matter more:
- "A competitor **in your zone** is now cheaper than you" (weighted higher than
  an undercut two zones away).
- "You're the most expensive in South-West this week."
Compute these in `report.py::compute_alerts` using the already-normalised
`Region` column.

### 2. Auto-derive the zone from the Booking.com address (medium)
Right now `region` is entered by hand. The Booking scraper already loads each
listing page — have it read the address/locality and pass it through
`resolve_zone()` as a fallback when `region` is omitted, so a new competitor is
zoned correctly with zero manual tagging.

### 3. Zone-level history & trend (medium)
The history files power per-property sparklines. Add a per-zone average series
so the dashboard can show "South-West average over the last 8 weeks" — the
single most useful line for a pricing decision. Data is already in the
snapshots; it's an aggregation + one more sparkline.

### 4. Seasonality / event awareness (medium, high payoff)
Madeira demand swings hard around fixed dates (New Year fireworks, Flower
Festival, Atlantic Festival, Christmas). A small `events.yaml` of date ranges,
surfaced as a banner on affected windows ("+90d overlaps New Year — expect
premium pricing"), would stop the report being read flat across very different
demand periods.

### 5. Occupancy-adjusted positioning (larger)
Price alone is half the picture. When the Airbnb provider supplies
`occupancy_pct`, plot price vs. occupancy per zone so you can see whether a
cheaper competitor is actually *filling* — i.e. whether you have room to raise.

### 6. Robustness & guardrails (ongoing)
- Cache the last-good scrape per competitor so a Booking markup change shows
  "stale (last seen 95 €)" instead of an empty cell.
- A tiny scraper health check in CI that fails loudly if >50% of prices come
  back empty (early warning that selectors broke).
- Currency normalisation if any competitor ever lists in a non-EUR currency.

### 7. Dashboard polish (small)
- Filter the table by zone (click a compass card → filter rows).
- A one-line "your position" summary at the top ("3rd cheapest of 6 in your
  zone; 4% under the South-West average").
- Show the zone on the map with a small inline SVG of Madeira.

---

*Zones are defined in `competitor_pricing/zones.py`; adjust the town lists or
add a zone there and everything downstream (config normalisation, report
grouping, dashboard order) follows automatically.*
