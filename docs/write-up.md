# FINN: the approach

*Built for the ENAM AI Engineer Build Challenge by DP, with Claude Code as the coding agent.*

## The problem, as I read it

Two different jobs share one product. A holder of 18 stocks does not want 50 exchange filings a day; they want to know, in three seconds, which of them they need to care about, and to be told when something crosses a line they chose. A researcher looking at a company they have never held wants to know whether management does what it says, without reading eight transcripts, and without a tool that makes things up.

Both fail the same way in practice: a summary that sounds right and is wrong. So the product is built around one rule: **a claim appears only with its source, and a number is never a model's guess.** Everything else follows from that.

## What I built

**Push.** A Morning Brief, groups of at most five cards ranked so that risks come before good news, routine filings collapsed into one row, and a finite end. Alerts compare end-of-day moves and chosen filing types with thresholds the user sets, and a change to a threshold changes the alerts instantly because the browser computes them from raw numbers. Two filing types get a real card: results (Revenue, EBITDA, PBT, PAT, QoQ and YoY, from the PDF itself) and management changes (who, role, date, and the filing's own profile of them).

**Pull.** Research on any NSE ticker: the last four earnings-call transcripts and the annual report are found on the exchange and read; what management said about the future is listed word for word with its page; a Promise Tracker judges each promise against later calls; and "Ask the documents" answers only from the filings, or says "Not found in the documents".


**How it looks and behaves.** The Brief opens with one line counted in code ("1 risk to review · Busy day: 6 of your companies filed", or "Quiet day"), then each company once with its filings under it in three lines: a bold headline, then a grey line with an icon, a short label, a reason of about eight words and a Risk, Watch or Good tag. Good and bad are soft tints with a 3px edge and a word or an arrow beside the colour, not loud fills. Everything else (the numbers, the PDF, the long reason) is one tap away. Alerts use the same window control as the Brief, show a calm dot on the tab instead of a count, and say why every alert fired, against the reader's own limit, and whether a filing from the same day explains the move. "You" is a profile without an account: a name kept only on the phone, the 18 companies with mute switches, preferences, and the three principles. Research opens with one counted line ("Delivered 2 of 5 promises that came due"), a stacked bar led by Missed, then the promises bad news first, each in three lines with a word-for-word excerpt and "Said in Q3 FY26 call → checked in Q2 FY27 call". Old data says it is old ("Latest highlights", "Data as of"), and on a quiet day the Brief looks further back and says so. The page is checked at 360 and 390 px, light and dark, with no sideways scroll and every text colour at 4.5:1 contrast or better, tints included.

**In rupees.** Most people do not think in percentages, so FINN can say it in rupees. In "My investments" (on the phone, never sent anywhere) a reader enters how much they have in each company and, if they know it, the average price they paid. With a buy price FINN shows profit and loss; without one, only today's move, never a made-up profit. The Brief gets a portfolio card (invested, worth now, overall, today, with a breakdown biggest loss first) and each company's header reads "Your ₹50,000 · ▼ ₹775 today · ▲ ₹4,200 overall". "Try with sample holdings" fills clearly labelled sample numbers. A "What if" calculator, in an open Brief card and at the top of every Research page, starts from that amount (else ₹10,000) and shows what today's move and the last 30 days' did to it, then a slider from −20% to +20% with quick chips: "If it moves −10%: you'd have ₹9,000 (▼ −₹1,000)". Every figure is the amount times a real close-to-close move, worked out in one tested helper; a gain is green with ▲ and a plus, a loss red with ▼ and a minus, and a grey note says which close it is based on and that it is for understanding only, not advice. It restates the past in rupees and forecasts nothing. Switching a company off in "Show in my brief" leaves it out of the Brief and Alerts.

**Following.** One search box on the Interested tab follows a company, a person (by exact full name) or one of ten topics, and a Following feed shows the filings that match, in the Brief's own cards with a grey "Because you follow ..." line, risks first, each filing once. It reads filings, never news, covers the 22 companies FINN tracks, and sends no push notification.

## Key decisions and trade-offs

**Rules before a model, everywhere a rule can do the job.** The exchange labels every filing, so most are classified without any model. A results PDF is read by word position, not by a model, because a model reading a table is how a wrong number gets onto a screen, and because a rule can be tested against the real filing line by line. I tested the extractor on seven very different real results filings (a lender, a PDF turned sideways, a company that prints its year-ago column second, two scans) and each ends in a correct card or an honest refusal. For a scan, a figure is shown only where Yahoo Finance's profit before tax confirms it.

**Make the lie impossible, not unlikely.** A model's quote is accepted only if it is word for word on the page it cites; the page comes from my own chunk, not from the model; a verdict needs a quote from a later call, or it is set back; when a promise is due is read by code from the speaker's words, and a number decides a verdict only if it is in the quotes; counts and the delivery rate are computed in code; an answer's figures must appear in its own quotes. A model that paraphrases, misnumbers or flatters cannot get a claim onto the screen.

**Say what you could not do.** A source that fails keeps the last good data and says how old it is. A scan nothing can confirm says "figures not shown". An engine that is asleep is "waking up". When no model has run, Research says "No verdict yet" and shows what management said instead. The model-dependent parts have now run live (15 Nov 2026) and the README says in a table what was checked and what was not.

**Find the bugs by reading real output.** The most useful tests were the ones that looked at real data. Reading the live results exposed an off-by-one in a column order (ITC prints its year-ago quarter second), a damaged profit row in a PDF, two regexes that had silently lost their word boundary, and a classifier that called a Vice-Chairman "a minor role". Reading real transcripts showed that management's answers carry no speaker label at all, so I stopped showing speaker names rather than misattribute words. A test of the rate limit showed that the library counted limits per URL, so changing the ticker reset the allowance.

**Trade-offs I chose on purpose.**
- *A quiet default looks further back.* The Brief opens on 24 hours, as the brief asks, but if that holds nothing material and the reader has not picked a window it looks back to 3 days, then 7, and says so. I found it by looking at the data: made on a Monday morning, the last 24 hours had nothing material and the results card was three days back. The cost is that "today" is sometimes not today; the page says so each time.
- *Two lines for a headline, not one.* A fact cut to fit one line is a fact cut mid-way. The cost is a slightly taller card.
- *A reason of about eight words, built by rules, not written by a model.* It is plainer and cheaper, and it can be clumsy ("Run off the specific" is a topic cut from a promise by rule). The longer reason is one tap away.
- *Counted in code, said in plain words.* "Delivered 2 of 5" is arithmetic on the verdicts; "Mostly delivers, but went quiet on 2 promises" is a fixed rule on the counts. A model never writes a number or a summary a reader could mistake for a finding.
- *A dot, not a count.* A count asks to be cleared; a dot says "look once". The price is that "new" means "since the data was refreshed", because without accounts there is no per-alert read state.
- *No accounts.* A name and every setting stay on the phone, which means no sync and no push notifications.

## Research behind the design

These are the findings the design leans on. FINN does not test them: they are reasons for the choices, not results of this project. Each figure below was checked against its source before it went in, and where the evidence comes from another field, or is only press commentary, I say so.

| Finding | What FINN does |
|---|---|
| When many companies report on the same day, investors react less to each one: attention is limited (Hirshleifer, Lim & Teoh, 2009) | A short, ranked Brief, and a "Busy day: N of your companies filed" line that says when attention is stretched |
| Investors who check their portfolios often feel losses more strongly and hold less equity: myopic loss aversion (Benartzi & Thaler, 1995; shown in private investors' survey data by Lee & Veld-Merkoulova, 2016) | One calm Brief with an end, "You're all caught up", not a feed to check |
| Investors look at their accounts less when they expect bad news (the ostrich effect; Karlsson, Loewenstein & Seppi, 2009), and logged in 9.5% less after a market decline (Sicherman, Loewenstein, Seppi & Utkus, 2016) | Risks first, and a line that says "N risks to review", so bad news is put in front of the reader, not left to be avoided |
| Individual investors tend to buy stocks that grab their attention (Barber & Odean, 2008) | Spike alerts are calm and give their reason; there is no buy button near an alert |
| Alerts get overridden: 93% of 2,455 visible medication alerts over four days (Bryant, Fletcher & Payne, 2014); 73.3% in a three-year inpatient study (Nanji et al., 2018) | A dot on the Alerts tab, not a count; a reason on every alert; routine filings in one collapsed row |
| Robinhood removed its confetti animation in March 2021 amid criticism of gamification (CNBC) | No confetti, streaks, scores or reward animations |
| Groww's minimal, jargon-free design for first-time investors (press commentary, not a usability study) | Three-line cards in plain words |
| Sparklines (Tufte); calm technology, information at the edge of attention that moves to the centre only when needed (Weiser & Brown, 1995) | The price trend is a small line behind a tap; the interface speaks when something needs it |

**What these do not show.** The medication studies are about doctors, not investors; I use them for one idea only, that a stream of alerts is overridden. The two attention studies describe what investors did, not what a brief like this would change. Nothing here claims FINN improves returns; the claim is narrower: it does not add to the noise.

**References** (only these; each checked):
- Hirshleifer, D., Lim, S. S., & Teoh, S. H. (2009). Driven to Distraction: Extraneous Events and Underreaction to Earnings News. *Journal of Finance*, 64(5), 2289–2325.
- Benartzi, S., & Thaler, R. H. (1995). Myopic Loss Aversion and the Equity Premium Puzzle. *Quarterly Journal of Economics*, 110(1), 73–92.
- Lee, B., & Veld-Merkoulova, Y. V. (2016). Myopic loss aversion and stock investments: An empirical study of private investors. *Journal of Banking & Finance*, 70, 235–246.
- Karlsson, N., Loewenstein, G., & Seppi, D. (2009). The ostrich effect: Selective attention to information. *Journal of Risk and Uncertainty*, 38(2), 95–115.
- Sicherman, N., Loewenstein, G., Seppi, D. J., & Utkus, S. P. (2016). Financial Attention. *Review of Financial Studies*, 29(4), 863–897. (The 9.5% is the fall in logins after a decline in the previous day's market; see the [Carnegie Mellon summary](https://www.cmu.edu/news/stories/archives/2015/december/ostrich-effect.html).)
- Barber, B. M., & Odean, T. (2008). All That Glitters: The Effect of Attention and News on the Buying Behavior of Individual and Institutional Investors. *Review of Financial Studies*, 21(2), 785–818.
- Bryant, A. D., Fletcher, G. S., & Payne, T. H. (2014). Drug interaction alert override rates in the Meaningful Use era: no evidence of progress. *Applied Clinical Informatics*. [PMC4187095](https://pmc.ncbi.nlm.nih.gov/articles/PMC4187095). (461 physicians, 18,354 orders, 2,455 visible alerts, 2,280 overridden.)
- Nanji, K. C., Seger, D. L., Slight, S. P., et al. (2018). Medication-related clinical decision support alert overrides in inpatients. *Journal of the American Medical Informatics Association*, 25(5), 476–481. [PubMed 29092059](https://pubmed.ncbi.nlm.nih.gov/29092059). (An inpatient study at a 793-bed teaching hospital, not an outpatient one.)
- CNBC, 31 March 2021: [Robinhood gets rid of confetti feature amid scrutiny over gamification of investing](https://www.cnbc.com/2021/03/31/robinhood-gets-rid-of-confetti-feature-amid-scrutiny-over-gamification.html).
- Groww: [YourStory, 2019, "First-time investors find simplicity of Groww"](https://yourstory.com/2019/05/first-time-investors-find-simplicity-of-groww) (press commentary).
- Tufte's sparklines. Weiser, M., & Brown, J. S. (1995). Designing Calm Technology.

## Efficiency

A model is used for three things only, with a cheap model by default and a strong one only for judging; every answer is cached by its input, the prompt version and the model; no whole document is sent; and every call is logged without the prompt or the key. Measured over the whole session: 222 successful calls (81 from the cache) and about 385,000 tokens in and 36,000 out, $0 on the free tier; details in [cost.md](cost.md).

## What I deliberately left out

- **Push notifications and accounts.** They need a server that holds who you are and where to reach you. FINN keeps a name and every setting on the phone, so there is nothing to sync and nothing to leak; the Alerts screen says plainly that alerts are checked when the app is opened.
- **News, broker notes and web search on the research side.** Research answers only from the company's own transcripts and annual report, so every claim can show its page. The management bio on a card is the filing's own profile, not a web search.
- **Company logos and people's photos.** Licensing, privacy and accuracy risk; a coloured initials badge carries the same meaning with none of it.
- **Investing, and alerts for what you follow.** Following a company, person or topic works on real filings, but sends no notification (that needs accounts). The Invest button is a labelled preview: a "coming soon" sheet with no order flow.
- **Gamification.** No streaks, scores, badges or reward animations. The Brief ends.
- **A language switch that does nothing.** The You tab says English is the only language today.

## Honest limits

- The Promise Tracker is more honest than its first run (24 of 54 Kept became 6 of 40) but not audited line by line. I read the decided verdicts against the transcripts and fixed what I found (a number reader that missed "INR2,400", a retrieval that missed "99acres"), but a few others may be wrong in the same ways. Most promises are "Too early", because most are about FY27, which has not ended.
- The strong model's free quota is 20 requests a day and ran out during re-runs, so most shipped verdicts were made by the cheap model (`gemini-3.5-flash-lite`); each record says which model answered. Re-running after the quota resets would use the strong one.
- Deployed, and research on a ticker that was never prepared works live because the engine falls back to NSE when BSE refuses Render (HTTP 403). It reads transcripts from NSE's filings; an annual report is not always among them (TITAN's was not), and the record says so.
- Neither Vercel nor Render deploys on `git push` (no GitHub link on either); deploys are triggered by hand.
- Naukri's 99acres billings promise was wrongly "Not followed up"; it is now Kept, with the Q2 FY27 call as evidence (page 5), re-read on the live site. TITAN, never prepared, researched live on Render in 34 seconds (four transcripts, 8 promises) with no annual report in NSE's feed.
- HAL files one transcript in 14 months, so no tracker is possible for it; Asian Paints' annual report is over the 25 MB limit and is skipped, and the record says so.
- Checked in a phone-sized browser at 360 and 390 px, not on a real phone. A promise's topic is cut from its own words by rule and is sometimes clumsy.
- Invest is a concept (a "coming soon" sheet). Following matches filings by exact name and by category or keywords, so a different spelling of a name will not match and a keyword rule can miss an unusual wording; it sends no push notifications, which need accounts.
- Lighthouse was not run (the environment would not let me download and run it); `scripts/perf_audit.py` measures the same load times and accessibility checks on the live site and is described as that, not as Lighthouse scores.

## Where I'd take it next

First, the engineering:

1. Re-run the Promise Tracker once the strong model's daily quota resets, and read every verdict against the transcripts again.
2. Add a second source for the annual report when NSE's feed has none (the filing lists on the company's own site).
3. Move the pipeline to a schedule once a server can reach the exchanges.
4. Add the consensus estimate for results, so a card can say "beat" or "missed" instead of only "up" or "down" against last year.

Then, the product:

1. **Any NSE company in the watchlist.** Following already works on real filings for the 22 companies FINN tracks (the Interested tab). Next: let a reader follow any NSE ticker (the pipeline would fetch its filings on demand), keep the list on a server once there are accounts, and give each company its own alert rules.
2. **Follow people, deeper, from primary sources.** Following a person today is an exact-name match in the filings of the 22 companies. The next version tracks a followed person through exchange filings by type: insider trades (SEBI PIT disclosures), substantial acquisitions (SAST), and management changes. Investor-alert tools such as Trendlyne sell this; FINN would build it from the filings themselves and show the filing as the source.
3. **Invest through a broker partner.** The "Invest" button is a placeholder. The model I'd test is a SEBI-registered broker partner that opens its own order screen from a company's page; FINN would earn a referral fee and never hold money or give advice. That is the revenue model.

4. **Rank by exposure.** "My investments" already keeps an amount per company on the phone, for the rupee line and the What if calculator. Next: rank the Brief by what each filing could do to that money, not by the filing's weight alone.
5. **A three-question first-time setup.** Which companies, how much attention, what counts as a risk; nothing else is asked.
6. **One brief a day, with quiet hours.** The calm dot is a first step; the next is a single daily time, and silence outside it.
7. **Hinglish across the app.** Fixed phrases in a dictionary, not machine translation; company names, numbers and quotes stay as filed.

The full record: [decisions](decisions.md) (24 up front, 137 while building), [data sources](data-sources.md) (what was verified, and what failed), and the [build log](build-log.md).
