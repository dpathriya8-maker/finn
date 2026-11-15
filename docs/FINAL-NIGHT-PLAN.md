# FINN: final night plan (autonomous)

You are the coding agent for FINN. Read `CLAUDE.md` first. This is the **last round of changes before submission in the morning**. The owner (DP) is asleep, so:

## Operating rules (read twice)
1. **Do not ask questions. Do not wait for approval.** Make the most reasonable decision, write it down in `docs/decisions.md`, and keep going.
2. **Work in order: Part 0 → A → B → C → D → E → F.** Each part is its own commit.
3. After **each** part that fully works:
   - run all tests (backend + frontend), type-check, lint and build, plus `scripts/check-secrets.sh`;
   - commit with a clear message, then `git push origin main`;
   - deploy the frontend: `npx vercel --prod` from `frontend/`;
   - if backend code changed, deploy Render through its API (RENDER_API_KEY from `.env`, never printed) and wait until it is live;
   - **verify on the live site** (https://finn-mocha.vercel.app): the page loads, no console errors, no sideways scroll at 360px and 390px in light and dark, and the part's feature works. Save a 390px screenshot of it in `docs/screens/`.
4. **Timebox: 60 minutes per part.** If a part isn't fully working by then, discard its uncommitted changes (`git checkout . && git clean -fd` inside the files you touched; never delete data or `.env`), note why in `docs/build-log.md`, and move to the next part. **Never leave the live site broken.** If a deploy breaks the live site, roll back to the previous commit's deploy immediately.
5. **Never revert earlier work** (calculator, My investments, research redesign, calm design, preview tabs, NSE fallback, etc.).
6. **Truth rules:** real data only; all money maths in code (one tested helper, shared with the calculator); every quote word for word with its page; anything not connected keeps a visible "Preview" badge; wherever money outcomes appear, show "For understanding only, not advice."
7. **Security:** never print, log or commit keys. Secrets stay in `.env`.
8. At the very end, write **`docs/NIGHT-REPORT.md`** (see Part F).

---

## Part 0: Make sure the calculator is in
- `git pull`. If the "What-if calculator" commit isn't on `main`, finish it first: amount field (prefilled from My investments, else ₹10,000); rows "Today (▼1.55%): −₹155" and "Last 30 days"; a −20%…+20% slider with chips −10/−5/+5/+10 → "you'd have ₹X (−₹Y)"; in expanded Brief cards and at the top of Research company pages; accessible; unit-tested.

## Part A: My portfolio, polished (profit and loss)
1. **You → My investments**, per company:
   - "Amount invested (₹)" plus an optional "Average buy price (₹)";
   - validated, Indian format (₹1,50,000), numeric keyboard on phones.
   - **With a buy price:** shares = amount ÷ buy price; value = shares × latest close; overall P&L = value − amount (₹ and %).
   - **Without a buy price:** show the invested amount and today's change only. No fake P&L.
2. **Portfolio summary card** at the top of the Invested tab, shown only if any amount is set:
   - Total invested · Current value · Overall ▲/▼ ₹ (%) · Today ▲/▼ ₹.
   - Tap → a per-company breakdown (value, P&L, weight %), **sorted biggest loss first**.
3. **Brief company header:** "Your ₹50,000 · ▼ ₹775 today · ▲ ₹4,200 overall". Show "overall" only if a buy price exists.
4. **"Try with sample holdings"** button:
   - fills clearly labelled SAMPLE amounts and buy prices;
   - a visible "Sample holdings" badge wherever they're used;
   - a "Clear" button;
   - never overwrites real entries without confirming.
5. **Unit tests:** profit, loss, zero, missing buy price, huge numbers, rounding to whole ₹.

## Part B: Follow companies, people and topics (filings only)
1. **Data.** The pipeline also fetches exchange filings for the research companies (`config/research.json`) for the same window, into a **separate** file in `frontend/public/data/` with the same item shape. The portfolio Brief stays unchanged. Run `python -m pipeline.run` from this laptop (BSE works here) and commit the data.
2. **Follow list** (stored in localStorage):
   - **Companies:** all portfolio + research companies.
   - **People:** names from management-change cards and people named in filings.
   - **Topics:** Results, Dividend, Fund raise, M&A, Management change, Credit rating, Orders & contracts, Capex, Legal, Pledging.
3. **Interested tab:**
   - One search box, "Follow a company, person or topic", plus chips for followed items with an unfollow (×).
   - A **"Following" feed:** filings in the window that match anything followed. Companies match by symbol; people by exact full name (case-insensitive, whole words) in the headline, subject or body; topics by category or keywords.
   - Cards use the 3-line style, risk first, with no duplicates, plus a grey "Because you follow <X>" line.
   - Honest empty states, e.g. "No filings about <name> in the last 7 days."
   - A grey note: "FINN follows filings from the 22 companies it tracks. Any NSE company is next."
   - Remove the "Preview" badge from following; **keep** it on Invest.
   - Always say "filings", never "news".

## Part C: Final polish
1. **Section boxes:** put each Brief and Interested section in a soft rounded box, with consistent padding and clear headers. Skip this if it breaks the layout.
2. Fix the stale check that expects 3 sections in the You tab (there are now 4+).
3. Polish copy: short, plain words, no jargon in collapsed views.

## Part D: Ready for graders (do this even if A–C were skipped)
1. **Stale-data safety:**
   - Count the 24h / 3d / 7d window back from the data's `generated_at`, **not the device clock**, so the Brief is never empty days later.
   - If the data is more than 24h old, the heading becomes "Latest highlights" and the line reads "Data as of <date, time>".
   - Do the same on Alerts.
2. **"60-second demo"** list, at the top of the README **and** in the email in `docs/submission.md`:
   1. Brief: open the Kaynes results card.
   2. Tap "Figures as printed" to see the source page.
   3. Research → Bajaj Finance: promises, misses first.
   4. Ask "What did they say about margins?"
   5. Research TITAN (wakes the free server, up to 2 min).
   6. You → "Try with sample holdings", then the calculator in a card.
3. **First visit only:** a dismissible hint on the Brief, "Tap any card for numbers and sources".
4. **Lighthouse (mobile)** on the live Brief and Research pages. Fix easy accessibility and performance issues, and put the scores in the README.

## Part E: Stronger good/bad colour (tints, not loud fills)
Apply on every card: Brief, Interested/Following, Alerts, Research promises and the portfolio summary.
- **Good / gains / Kept:** soft green tinted card + 3px green left border + green label and ▲ numbers.
- **Risk / losses / Missed:** soft red tint + 3px red left border + red label and ▼ numbers.
- **Watch / Partly / Not followed up:** soft amber tint + amber border.
- **Neutral / routine:** no tint.
- Summary line: "N risk(s) to review" in red, "Quiet day" in green.
- Portfolio summary: values coloured by direction.

Rules:
- Tint opacity about 8–12% in light mode, 14–18% in dark.
- Text contrast at least 4.5:1 on every tint.
- Always keep the ▲▼ arrow or a text label next to the colour.
- Indigo stays for buttons and tabs only.

## Part F: Refresh, docs, final verification (always do this)
1. **Fresh data:** run `python -m pipeline.run` (and `python -m pipeline.research` only if it's needed and the free quota allows), then commit the data. The Brief should show the latest filings.
2. **Docs:**
   - README: what it does, the 60-second demo, the "what is verified" table, Lighthouse scores, and screenshots retaken from the **live** site at 390px.
   - `docs/write-up.md`, `docs/decisions.md`, `docs/build-log.md`.
   - The email in `docs/submission.md`: everything built tonight moves into "What I built", and "Next" and "Known limits" match reality.
3. **Final checks:**
   - All tests pass and the secret check is clean.
   - The live site is on the final commit and shows "Engine online".
   - No console errors on any screen.
   - No sideways scroll at 360px or 390px, light or dark.
   - Brief, Alerts, Research (Bajaj + TITAN live), Ask, You and the calculator all work.
4. Commit, push, deploy and verify one last time.
5. Write **`docs/NIGHT-REPORT.md`**, then commit and push it. It must contain:
   - **Done / skipped / reverted**, per part, with commit hashes.
   - **Live check results**: what you verified and how.
   - **Known problems**, stated plainly.
   - **EMAIL LINES**: the exact text DP should paste into the email for *What I built*, *Where I'd take it next*, *Known limits* and the *60-second demo*.
   - **MORNING CHECKLIST** for DP (5 lines max).
