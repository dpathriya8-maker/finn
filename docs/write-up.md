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

**Make the lie impossible, not unlikely.** A model's quote is accepted only if it is word for word on the page it cites; the page comes from my own chunk, not from the model; a verdict other than "Too early" needs a quote from a later call, or it is set back; counts and the delivery rate are computed in code; an answer's figures must appear in its own quotes. A model that paraphrases, misnumbers or flatters cannot get a claim onto the screen.

**Say what you could not do.** A source that fails keeps the last good data and says how old it is. A scan nothing can confirm says "figures not shown". An engine that is asleep is "waking up". When no model has run, Research says "No verdict yet" and shows what management said instead. I did not have API keys, so the model-dependent parts are built and tested against a scripted model but never run live, and the README says so in a table.

**Find the bugs by reading real output.** The most useful tests were the ones that looked at real data. Reading the live results exposed an off-by-one in a column order (ITC prints its year-ago quarter second), a damaged profit row in a PDF, two regexes that had silently lost their word boundary, and a classifier that called a Vice-Chairman "a minor role". Reading real transcripts showed that management's answers carry no speaker label at all, so I stopped showing speaker names rather than misattribute words. A test of the rate limit showed that the library counted limits per URL, so changing the ticker reset the allowance.

## Efficiency

A model is used for three things only, with a cheap model by default and a strong one only for judging; every answer is cached by its input, the prompt version and the model; no whole document is sent; and every call is logged without the prompt or the key. About seven calls per company for the whole tracker. Measured so far: zero, because there are no keys. The report command is built.

## Honest limits

- The Promise Tracker's verdicts and written answers have not run against a live model.
- It is not deployed yet. BSE and NSE are only proven reachable from a home connection, so on a server an unprepared ticker may fail, with a stated reason; the four prepared companies do not depend on it.
- HAL files one transcript in 14 months, so no tracker is possible for it; Asian Paints' annual report is over the 25 MB limit and is skipped, and the record says so.
- No push notifications: they need accounts. The Alerts screen says so.

## What I would do next

1. Put a key in `.env`, run `python -m pipeline.research`, read the first real verdicts against the transcripts line by line, and tune the two prompts. This is the first thing to do.
2. Deploy, then fill in the "Render" column of the data-source table with what the exchanges really allow from a server.
3. Move the pipeline to a schedule once a server can reach the exchanges.
4. Add the consensus estimate for results, so a card can say "beat" or "missed" instead of only "up" or "down" against last year.

The full record: [decisions](decisions.md) (24 up front, 84 while building), [data sources](data-sources.md) (what was verified, and what failed), and the [build log](build-log.md).
