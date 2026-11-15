# FINN: the approach

*Built for the ENAM AI Engineer Build Challenge by DP, with Claude Code as the coding agent.*

## The problem, as I read it

Two different jobs share one product. A holder of 18 stocks does not want 50 exchange filings a day; they want to know, in three seconds, which of them they need to care about, and to be told when something crosses a line they chose. A researcher looking at a company they have never held wants to know whether management does what it says, without reading eight transcripts, and without a tool that makes things up.

Both fail the same way in practice: a summary that sounds right and is wrong. So the product is built around one rule: **a claim appears only with its source, and a number is never a model's guess.** Everything else follows from that.

## What I built

**Push.** A Morning Brief, groups of at most five cards ranked so that risks come before good news, routine filings collapsed into one row, and a finite end. Alerts compare end-of-day moves and chosen filing types with thresholds the user sets, and a change to a threshold changes the alerts instantly because the browser computes them from raw numbers. Two filing types get a real card: results (Revenue, EBITDA, PBT, PAT, QoQ and YoY, from the PDF itself) and management changes (who, role, date, and the filing's own profile of them).

**Pull.** Research on any NSE ticker: the last four earnings-call transcripts and the annual report are found on the exchange and read; what management said about the future is listed word for word with its page; a Promise Tracker judges each promise against later calls; and "Ask the documents" answers only from the filings, or says "Not found in the documents".

## The decisions that mattered

**Rules before a model, everywhere a rule can do the job.** The exchange labels every filing, so most are classified without any model. A results PDF is read by word position, not by a model, because a model reading a table is how a wrong number gets onto a screen, and because a rule can be tested against the real filing line by line. I tested the extractor on seven very different real results filings (a lender, a PDF turned sideways, a company that prints its year-ago column second, two scans) and each ends in a correct card or an honest refusal. For a scan, a figure is shown only where Yahoo Finance's profit before tax confirms it.

**Make the lie impossible, not unlikely.** A model's quote is accepted only if it is word for word on the page it cites; the page comes from my own chunk, not from the model; a verdict needs a quote from a later call, or it is set back; when a promise is due is read by code from the speaker's words, and a number decides a verdict only if it is in the quotes; counts and the delivery rate are computed in code; an answer's figures must appear in its own quotes. A model that paraphrases, misnumbers or flatters cannot get a claim onto the screen.

**Say what you could not do.** A source that fails keeps the last good data and says how old it is. A scan nothing can confirm says "figures not shown". An engine that is asleep is "waking up". When no model has run, Research says "No verdict yet" and shows what management said instead. The model-dependent parts have now run live (15 Nov 2026) and the README says in a table what was checked and what was not.

**Find the bugs by reading real output.** The most useful tests were the ones that looked at real data. Reading the live results exposed an off-by-one in a column order (ITC prints its year-ago quarter second), a damaged profit row in a PDF, two regexes that had silently lost their word boundary, and a classifier that called a Vice-Chairman "a minor role". Reading real transcripts showed that management's answers carry no speaker label at all, so I stopped showing speaker names rather than misattribute words. A test of the rate limit showed that the library counted limits per URL, so changing the ticker reset the allowance.

## Efficiency

A model is used for three things only, with a cheap model by default and a strong one only for judging; every answer is cached by its input, the prompt version and the model; no whole document is sent; and every call is logged without the prompt or the key. Measured over the whole session: 210 successful calls (75 from the cache) and about 367,000 tokens in and 35,000 out, $0 on the free tier; details in [cost.md](cost.md).

## Honest limits

- The Promise Tracker is more honest than its first run (24 of 54 Kept became 5 of 40) but not audited line by line. One verdict I know is wrong: Naukri's "billings growth to recover in Q1" (about 99acres) shows Not followed up although the Q1 call discusses 99acres billings; the search did not surface that passage. Most promises are "Too early" because most are about FY27, which has not ended.
- The strong model's free quota is 20 requests a day and ran out during re-runs, so the shipped verdicts were made by the cheap model (`gemini-3.5-flash-lite`); each record says which model answered. Re-running after the quota resets would use the strong one.
- Deployed, but **BSE answers HTTP 403 from Render**, so research on an unprepared ticker (TITAN) fails there with a stated reason; Yahoo, NSE and screener.in do work from the server, so a fallback that resolves a company from NSE alone is the obvious next step. The four prepared companies do not depend on it.
- HAL files one transcript in 14 months, so no tracker is possible for it; Asian Paints' annual report is over the 25 MB limit and is skipped, and the record says so.
- No push notifications: they need accounts. The Alerts screen says so.

## What I would do next

1. Re-run the Promise Tracker once the strong model's daily quota resets, and read the verdicts against the transcripts again; fix the retrieval gap behind the Naukri case (search with the subject named earlier in the passage).
2. Let the live engine resolve a company from NSE alone when BSE refuses the server, so an unprepared ticker works from Render.
3. Move the pipeline to a schedule once a server can reach the exchanges.
4. Add the consensus estimate for results, so a card can say "beat" or "missed" instead of only "up" or "down" against last year.

The full record: [decisions](decisions.md) (24 up front, 84 while building), [data sources](data-sources.md) (what was verified, and what failed), and the [build log](build-log.md).
