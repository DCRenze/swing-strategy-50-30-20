# PEAD Long Leg via Earnings Announcement Return (EAR) Proxy
- Agent: D (Academic & quant literature)
- Sources: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=909563 — Brandt, Kishore, Santa-Clara & Venkatachalam, "Earnings Announcements are Full of Surprises," 2008 (also https://quantpedia.com/www/Earnings_Announcements_are_Full_of_Surprises.pdf)
  https://quantpedia.com/strategies/post-earnings-announcement-effect — Quantpedia, "Post-Earnings Announcement Effect"
  https://en.wikipedia.org/wiki/Post%E2%80%93earnings-announcement_drift — PEAD overview (Ball & Brown 1968; Bernard & Thomas 1989 lineage)
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3111607 — Martineau, "Rest in Peace Post-Earnings Announcement Drift," Critical Finance Review 2022
  https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/ — UCLA Anderson Review on the 2025 PEAD-revival debate
- Thesis: Investors underreact to the information in earnings announcements, so prices drift in the direction of the surprise for weeks afterward. Brandt et al. show the market's own 3-day price reaction (EAR) is a better, fully price-based surprise measure than analyst/seasonal-walk SUE — making the trigger observable from OHLCV + earnings dates alone.
- Entry rules:
  - Universe: NYSE/AMEX/NASDAQ ex-financials/utilities, price > $5 (paper spec).
  - For each stock reporting earnings, compute EAR = cumulative return over the 3-day window centered on the announcement date, minus the return of a matched benchmark (paper uses size/BM-matched portfolio; using SPY or sector ETF as benchmark is MY simplification).
  - Buy stocks whose EAR falls in the top quintile of the trailing quarter's EAR distribution (paper uses previous-quarter breakpoints to avoid look-ahead).
  - Entry at the open/close of the 2nd day after the announcement (paper spec).
  - Optional volume confirmation (MY addition, proxying high SUE without fundamentals): announcement-day volume >= 2x 50-day average.
- Exit rules: Paper holds 60 trading days. ADAPTATION for swing horizon (mine): hold 10-15 trading days — PEAD literature shows drift is front-loaded after the announcement; expect to capture only a fraction of the 60-day drift.
- Indicators & parameters: EAR window = [-1, +1] days around announcement; quintile breakpoints from prior quarter; entry day +2; documented hold 60 days; long leg = top EAR quintile (paper's strongest variant intersects top EAR with top SUE quintile).
- Claimed performance: L/S EAR quintile spread ~7.55%/yr abnormal return; combined EAR+SUE strategy ~12.5%/yr abnormal; long leg of the combined sort earned ~2.97% abnormal per 60-day quarter (~12% annualized), sample 1987-2004, GROSS of costs. Quantpedia replication: ~15% p.a. for the L/S version, max DD -11.2%.
- Evidence quality: 3 (methodology is strong and peer-reviewed lineage is deep, but post-publication decay evidence is direct and severe)
- Long-only fit: partial — documented as L/S quintile spread, but the long leg (top-quintile EAR) has standalone documented abnormal returns.
- 2-15 day fit: partial — documented hold is 60 days; 10-15 day truncation is my adaptation, justified by front-loaded drift but not separately tabulated in this paper.
- Codability: yes — needs daily OHLCV + earnings announcement dates (and a benchmark series); no fundamentals or analyst data.
- Notes: DECAY IS THE CENTRAL RISK: Martineau (2022) shows PEAD vanished in non-microcap stocks around 2001-2006 (decimalization, Reg NMS, HFT arbitrage); it persisted longest only in microcaps. Two 2025 papers contest this, but the disagreement hinges on including microcaps and on surprise definitions — for a liquid-stock pipeline, assume the classical effect is mostly arbitraged. Brandt et al. results are gross of costs and strongest in small caps. The realistic liquid-stock edge, if any, is a few-day continuation after very large positive announcement reactions, not the textbook 60-day drift. Event-driven turnover is moderate (one trade per stock per quarter), which helps cost survival.
