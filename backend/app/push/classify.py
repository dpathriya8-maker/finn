"""Rules-first announcement classifier (BSE category/subcategory plus keywords); cheap LLM only if ambiguous.

Tier 0, no model: an exact label table for each exchange decides most filings. Only the vague labels
(BSE "General", NSE "Updates", board-meeting outcomes) are read by keyword, and then the matching rule
for the most serious category wins, because a risk should never be hidden behind a harmless-sounding
match. A refiner then moves good and bad news apart inside a category (a downgrade outranks a
reaffirmation; a CFO resignation outranks an appointment).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from app.push.categories import load as categories


@dataclass(frozen=True)
class Classification:
    category: str
    routine: bool = False  # this rule marks the filing routine even if its category normally is not
    adjust: int = 0  # added to the category weight when scoring: bad news up, boring or good news down
    note: str = ""  # why the adjustment was made; shown on the card
    rule: str = ""  # which rule decided, kept for transparency and debugging
    tone: str = "neutral"  # bad | watch | good | neutral: the only thing that may be coloured in the app


@dataclass(frozen=True)
class Entry:
    result: Classification
    read_text: bool = False  # True: the label is too vague, so keyword rules get the first say


def E(category: str, *, routine: bool = False, adjust: int = 0, note: str = "", read: bool = False, tone: str = "neutral") -> Entry:
    return Entry(Classification(category, routine, adjust, note, tone=tone), read)


def _t(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.I)


# ---------------------------------------------------------------------------------------------------
# Exact labels. Key: (BSE category, BSE subcategory). Seen on a full trading day plus 90 days of 8 companies.
# ---------------------------------------------------------------------------------------------------
BSE_LABELS: dict[tuple[str, str], Entry] = {
    ("Result", "Financial Results"): E("results"),
    ("Board Meeting", "Outcome of Board Meeting"): E("unclassified", read=True, note="Board meeting outcome"),
    ("Board Meeting", "Board Meeting"): E("agm_egm", note="Board meeting date announced"),
    ("AGM/EGM", "AGM"): E("agm_egm"),
    ("AGM/EGM", "EGM"): E("agm_egm"),
    ("AGM/EGM", "Postal Ballot"): E("postal_ballot"),
    ("Insider Trading / SAST", "Closure of Trading Window"): E("insider_trading"),
    ("Insider Trading / SAST", "Disclosures under Reg. 29(2) of SEBI (SAST) Regulations, 2011"): E("insider_trading"),
    ("Corp. Action", "Dividend"): E("dividend"),
    ("Corp. Action", "Record Date"): E("dividend", read=True),
    ("Corp. Action", "Bonus"): E("bonus_split"),
    ("Corp. Action", "Sub-division / Stock Split"): E("bonus_split"),
    ("Corp. Action", "Bonds / Right issue"): E("fund_raise"),
    ("Corp Action", "Dividend Updates"): E("dividend", routine=True, note="Dividend follow-up"),
    ("Corp Action", "Daily Buy Back of equity shares"): E("dividend", routine=True, note="Daily buy-back report"),
    ("Others", ""): E("unclassified", read=True),
    ("Others", "Outcome without intimation"): E("unclassified", read=True),
    ("Others", "Reg. 34 (1) Annual Report"): E("agm_egm", routine=True, note="Annual report filed"),
    ("Others", "Intimation of Repayment of Commercial Paper (CP)"): E("unclassified", routine=True, note="Debt repayment notice"),
    ("Others", "Reg. 54 - Asset Cover details"): E("unclassified", routine=True, note="Routine compliance filing"),
    # Company Update
    ("Company Update", "General"): E("unclassified", read=True),
    ("Company Update", "Analyst / Investor Meet"): E("investor_meetings"),
    ("Company Update", "Investor Presentation"): E("investor_meetings"),
    ("Company Update", "Earnings Call Transcript"): E("earnings_call", note="Call transcript"),
    ("Company Update", "Newspaper Publication"): E("press_release", routine=True, note="Newspaper copy of an earlier filing"),
    ("Company Update", "Press Release / Media Release"): E("press_release", read=True),
    ("Company Update", "Press Release / Media Release (Revised)"): E("press_release", read=True),
    ("Company Update", "Award of Order / Receipt of Order"): E("press_release", adjust=8, note="Order win"),
    ("Company Update", "Change in Management"): E("management_change"),
    ("Company Update", "Change in Directorate"): E("management_change"),
    ("Company Update", "Resignation of Director"): E("management_change"),
    ("Company Update", "Resignation of Chief Financial Officer (CFO)"): E("management_change"),
    ("Company Update", "Resignation of Chief Executive Officer (CEO)"): E("management_change"),
    ("Company Update", "Resignation of Chairman and Managing Director"): E("management_change"),
    ("Company Update", "Resignation of Statutory Auditors"): E("management_change"),
    ("Company Update", "Resignation of Company Secretary / Compliance Officer"): E("management_change"),
    ("Company Update", "Appointment of Statutory Auditor/s"): E("management_change"),
    ("Company Update", "Appointment of Company Secretary / Compliance Officer"): E("management_change"),
    ("Company Update", "Cessation"): E("management_change"),
    ("Company Update", "Retirement"): E("management_change"),
    ("Company Update", "Credit Rating"): E("credit_rating"),
    ("Company Update", "Acquisition"): E("m_and_a"),
    ("Company Update", "Scheme of Arrangement"): E("m_and_a"),
    ("Company Update", "Diversification / Disinvestment"): E("m_and_a"),
    ("Company Update", "Joint Venture"): E("m_and_a"),
    ("Company Update", "Restructuring"): E("m_and_a"),
    ("Company Update", "Open Offer"): E("m_and_a"),
    ("Company Update", "Public Announcement"): E("m_and_a"),
    ("Company Update", "Raising of Funds"): E("fund_raise"),
    ("Company Update", "Issue of Securities"): E("fund_raise"),
    ("Company Update", "Qualified Institutional Placement"): E("fund_raise"),
    ("Company Update", "Preferential Issue"): E("fund_raise"),
    ("Company Update", "Allotment of Equity Shares"): E("fund_raise"),
    ("Company Update", "Allotment of ESOP / ESPS"): E("fund_raise", routine=True, note="Employee share allotment"),
    ("Company Update", "Monitoring Agency Report"): E("fund_raise", routine=True, note="Routine fund-use report"),
    ("Company Update", "Reg. 32 (1), (3) - Statement of Deviation & Variation"): E("fund_raise", routine=True, note="Routine fund-use report"),
    ("Company Update", "Buy back"): E("dividend", note="Share buy-back"),
    ("Company Update", "Post Buyback Public Announcement"): E("dividend", routine=True, note="Buy-back follow-up"),
    ("Company Update", "Intimation of meeting of Committee of Creditors"): E("litigation", note="Insolvency process", tone="bad"),
    ("Company Update", "Strikes /Lockouts / Disturbances"): E("unclassified", adjust=28, note="Operations may be disrupted", tone="watch"),
    ("Company Update", "Clarification"): E("unclassified", read=True, adjust=15, note="Clarification given to the exchange", tone="watch"),
    ("Company Update", "Board Meeting Rescheduled"): E("agm_egm", note="Board meeting rescheduled"),
    ("Company Update", "Meeting Updates"): E("agm_egm"),
    ("Company Update", "Revision of outcome"): E("agm_egm", note="Earlier outcome revised"),
    ("Company Update", "Code of Conduct under SEBI (PIT) Regulations, 2015"): E("insider_trading"),
    ("Company Update", "Amendments to Memorandum & Articles of Association"): E("unclassified", routine=True, note="Routine compliance filing"),
    ("Company Update", "Certificate under Reg. 74 (5) of SEBI (DP) Regulations, 2018"): E("unclassified", routine=True, note="Routine compliance filing"),
    ("Company Update", "Change in Registered Office Address"): E("unclassified", routine=True, note="Routine compliance filing"),
    ("Company Update", "Reg.24(A)-Annual Secretarial Compliance"): E("unclassified", routine=True, note="Routine compliance filing"),
    ("Company Update", "Memorandum of Understanding /Agreements"): E("m_and_a", note="Agreement signed"),
    ("Company Update", "Trading Plan under SEBI (PIT) Regulations, 2015"): E("insider_trading"),
    ("Company Update", "Resignation of Managing Director"): E("management_change"),
    ("Others", "Business Responsibility and Sustainability Reporting (BRSR)"): E("unclassified", routine=True, note="Sustainability report filed"),
    ("Others", "Half Yearly Report (SEBI Circular No. CIR/IMD/DF-1/67/2017)"): E("unclassified", routine=True, note="Routine compliance filing"),
    (
        "Others",
        "Format of the Initial Disclosure to be made by an entity identified as a Large Corporate : Annexure A",
    ): E("unclassified", routine=True, note="Routine compliance filing"),
}

# Exact labels. Key: NSE `desc`.
NSE_LABELS: dict[str, Entry] = {
    "Analysts/Institutional Investor Meet/Con. Call Updates": E("investor_meetings"),
    "Investor Presentation": E("investor_meetings"),
    "Outcome of Board Meeting": E("unclassified", read=True, note="Board meeting outcome"),
    "Updates": E("unclassified", read=True),
    "General Updates": E("unclassified", read=True),
    "Others": E("unclassified", read=True),
    "Press Release": E("press_release", read=True),
    "Press Release (Revised)": E("press_release", read=True),
    "Copy of Newspaper Publication": E("press_release", routine=True, note="Newspaper copy of an earlier filing"),
    "Integrated Filing- Financial": E("results"),
    "Reasons for Delayed/Non-submission of Financial Results": E("litigation", note="Results delayed or not filed: a red flag", tone="bad"),
    "Pendency of Litigation(s)/dispute(s) or the outcome impacting the Company": E("litigation", tone="bad"),
    "Action(s) taken or orders passed": E("litigation", tone="bad"),
    "Appointment": E("management_change"),
    "Resignation": E("management_change"),
    "Resignation of Director/KMP/SMP": E("management_change"),
    "Resignation of Statutory Auditor": E("management_change"),
    "Change in Auditors": E("management_change"),
    "Change in Management": E("management_change"),
    "Change in Director(s)": E("management_change"),
    "Change in Company Secretary/Compliance Officer": E("management_change"),
    "Cessation": E("management_change"),
    "Retirement": E("management_change"),
    "Acquisition": E("m_and_a"),
    "Scheme of Arrangement": E("m_and_a"),
    "Other Restructuring": E("m_and_a"),
    "Open Offer": E("m_and_a"),
    "Allotment of Securities": E("fund_raise", read=True),
    "ESOP/ESOS/ESPS": E("fund_raise", routine=True, note="Employee share allotment"),
    "Options to purchase securities": E("fund_raise", routine=True, note="Employee share options"),
    "Monitoring Agency Report": E("fund_raise", routine=True, note="Routine fund-use report"),
    "Statement of deviation(s) or variation(s) under Reg. 32": E("fund_raise", routine=True, note="Routine fund-use report"),
    "Utilisation of Funds": E("fund_raise", routine=True, note="Routine fund-use report"),
    "Credit Rating": E("credit_rating"),
    "Credit Rating- Revision": E("credit_rating"),
    "Credit Rating- Others": E("credit_rating"),
    "Dividend": E("dividend"),
    "Record Date": E("dividend", read=True),
    "Bonus": E("bonus_split"),
    "Stock split": E("bonus_split"),
    "Buyback": E("dividend", note="Share buy-back"),
    "Post Buyback Public Announcement": E("dividend", routine=True, note="Buy-back follow-up"),
    "Bagging/Receiving of orders/contracts": E("press_release", adjust=8, note="Order win"),
    "Capacity addition": E("capex"),
    "Commencement of commercial production/operations": E("capex"),
    "Spurt in Volume": E("unclassified", adjust=22, note="The exchange asked the company to explain a volume spurt", tone="watch"),
    "News Verification": E("unclassified", adjust=22, note="The exchange asked the company to confirm a news report", tone="watch"),
    "Disruption of Operations": E("unclassified", adjust=28, note="Operations may be disrupted", tone="watch"),
    "Disclosure of material issue": E("unclassified", read=True, adjust=10, note="Company flagged a material issue"),
    "Giving guarantees/indemnity/ becoming a surety for third party": E("unclassified", adjust=12, note="Company is guaranteeing a third party", tone="watch"),
    "Shareholders meeting": E("agm_egm"),
    "Committee Meeting Updates": E("agm_egm"),
    "Trading Window": E("insider_trading"),
    "Related Party Transactions": E("unclassified", routine=True, note="Routine compliance filing"),
    "Corrigendum": E("unclassified", routine=True, note="Correction to an earlier filing"),
    "Name Change": E("unclassified", routine=True, note="Routine compliance filing"),
    "Loss of Share Certificates": E("unclassified", routine=True, note="Routine compliance filing"),
    "Amendment to AOA/MOA": E("unclassified", routine=True, note="Routine compliance filing"),
    "Certificate under SEBI (Depositories and Participants) Regulations, 2018": E("unclassified", routine=True, note="Routine compliance filing"),
}

# ---------------------------------------------------------------------------------------------------
# Keyword rules, read only for vague labels. Several can match; the most serious category wins.
# ---------------------------------------------------------------------------------------------------
_MGMT_ROLE = r"chief|cfo\b|ceo\b|managing director|whole[- ]time|chairman|chairperson|key managerial|kmp\b|statutory auditor|company secretary|compliance officer|director"
TEXT_RULES: list[tuple[str, re.Pattern[str], Classification]] = [
    ("text:transcript", _t(r"transcript"), Classification("earnings_call", note="Call transcript")),
    (
        "text:litigation",
        _t(
            r"\b(litigation|tribunal|nclt|nclat|show[- ]cause|penalt(?:y|ies)|adjudicat\w+|sebi order|order passed|"
            r"demand notice|search and seizure|enforcement directorate|summons|injunction|insolvency|cirp|"
            r"high court|supreme court|non-?submission of financial results|income[- ]tax (?:demand|department)|"
            r"gst (?:demand|notice))\b"  # a subsidiary's "voluntary winding up" is restructuring, not litigation
        ),
        Classification("litigation", tone="bad"),
    ),
    ("text:pledge", _t(r"pledge|encumbr"), Classification("pledging", tone="watch")),
    (
        "text:results",
        _t(
            r"(?:un)?audited .{0,40}results?|financial results? (?:for|of|as on)|results for the (?:quarter|half|year|period)|"
            r"approv\w+ .{0,60}results?|integrated (?:financial )?results?|(?:quarter|half[- ]year|year)ly? results"
        ),
        Classification("results"),
    ),
    (
        "text:credit",
        _t(r"credit rating|\b(?:crisil|icra|care ratings|india ratings|acuite|brickwork|ind-ra)\b"),
        Classification("credit_rating"),
    ),
    (
        "text:management",
        _t(
            r"resign\w*|cessation of|ceases to|demise|passed away|steps? down|"
            r"change in (?:the )?(?:management|director\w*|auditors?|key managerial)|"
            rf"(?:re-?)?appoint\w*.{{0,80}}(?:{_MGMT_ROLE})"
        ),
        Classification("management_change"),
    ),
    (
        "text:m_and_a",
        _t(
            r"acqui(?:re|sition|ring)|merger|amalgamation|demerger|scheme of arrangement|joint venture|slump sale|"
            r"takeover|open offer|divest\w*|disinvest\w*|share purchase agreement|shareholders'{0,2} agreement|"
            r"asset purchase agreement|business transfer agreement|memorandum of understanding|\bmou\b"
        ),
        Classification("m_and_a"),
    ),
    (
        "text:fund_raise",
        _t(
            r"fund[- ]?raising|raising of funds|\bqip\b|qualified institutions? placement|preferential (?:issue|allotment)|"
            r"initial public offer\w*|\bipo\b|"
            r"rights issue|issue of (?:equity|shares|securities|debentures|bonds|ncds?|warrants)|non-?convertible debentures?|"
            r"\bncds?\b|external commercial borrowing|\becb\b|allotment of (?:equity|shares|securities|ncds?|warrants)"
        ),
        Classification("fund_raise"),
    ),
    ("text:bonus_split", _t(r"bonus (?:issue|shares?)|issue of bonus|stock split|sub-?division of (?:equity )?shares"), Classification("bonus_split")),
    ("text:buyback", _t(r"buy-?back"), Classification("dividend", note="Share buy-back")),
    ("text:dividend", _t(r"\bdividend\b"), Classification("dividend")),
    (
        "text:capex",
        _t(
            r"capex|capital expenditure|new (?:plant|facility|factory|unit)|capacity (?:addition|expansion)|expansion of|"
            r"greenfield|brownfield|commencement of commercial production"
        ),
        Classification("capex"),
    ),
    (
        "text:orders",
        _t(r"award of (?:order|contract)|receipt of (?:an )?orders?|bagging|letter of (?:award|intent)|work order|secured (?:an )?orders?"),
        Classification("press_release", adjust=8, note="Order win"),
    ),
    (
        "text:disruption",
        _t(r"\bstrikes?\b|lock-?out|fire (?:at|broke)|accident|shutdown|disruption of operations|force majeure|explosion|flood|cyber ?(?:attack|incident)|ransomware"),
        Classification("unclassified", adjust=28, note="Operations may be disrupted", tone="watch"),
    ),
    (
        "text:exchange_query",
        _t(r"spurt in volume|price movement|clarification (?:on|regarding|sought)|news verification|rumou?rs?"),
        Classification("unclassified", adjust=22, note="The exchange asked the company to explain", tone="watch"),
    ),
    (
        "text:investor",
        _t(
            r"analysts?\b|investor meet|institutional investors?|conference call|earnings call|investor presentation|"
            r"shareholder letter|letter to (?:the )?shareholders|results presentation"
        ),
        Classification("investor_meetings"),
    ),
    (
        "text:insider",
        _t(r"trading window|insider trading|prohibition of insider|pit regulations|takeover regulations|\bsast\b|regulation 29|regulation 7\(2\)"),
        Classification("insider_trading"),
    ),
    (
        "text:agm",
        _t(r"annual general meeting|\bagm\b|extra-?ordinary general meeting|\begm\b|postal ballot|e-voting|scrutini[sz]er|book closure"),
        Classification("agm_egm"),
    ),
    ("text:newspaper", _t(r"newspaper"), Classification("press_release", routine=True, note="Newspaper copy of an earlier filing")),
    ("text:press", _t(r"press release|media release|(?:^|\W)release\s*[-–:]|a release on"), Classification("press_release")),
    (
        "text:compliance",
        _t(
            r"regulation 74|reg\.? 74|compliance certificate|certificate under|statement of deviation|monitoring agency|"
            r"asset cover|loss of share certificates?|duplicate share|investor complaints?|grievance|shareholding pattern|"
            r"related party transactions?|corrigendum|name change|change in registered office|memorandum of association|"
            r"articles of association|code of conduct|disclosure of voting|scrutinizer|registrar and transfer agent|\brta\b|"
            r"secretarial compliance|materiality of information|authori[sz]ation to determine|"
            r"communication received from (?:the )?stock exchanges?|reg\.? ?24\(?a\)?|brsr|business responsibility"
        ),
        Classification("unclassified", routine=True, note="Routine compliance filing"),
    ),
]

# ---------------------------------------------------------------------------------------------------
# Refiners: inside a category, pull bad news up and good or empty news down. First match wins.
# (regex, adjust, routine?, note, tone)
# ---------------------------------------------------------------------------------------------------
_EXIT = r"resign\w*|cessation|ceases|ceased|demise|passed away|removal|terminat\w+|steps? down|relinquish\w*"
_KEY_ROLE = r"chief financial officer|\bcfo\b|chief executive officer|\bceo\b|managing director|chairman|chairperson|statutory auditors?|chief operating officer|\bcoo\b"
# "Non-Independent Director" is not an independent director: without the lookbehinds, Tata Steel's Vice-Chairman was "a minor role".
_MINOR_ROLE = r"company secretary|compliance officer|(?<!non-)(?<!non )independent director|additional director|cost auditor|secretarial auditor|internal auditor"
REFINERS: dict[str, list[tuple[re.Pattern[str], int, bool, str, str]]] = {
    "credit_rating": [
        (_t(r"downgrad\w*|negative outlook|outlook (?:to|revised to|changed to) negative|watch with negative|default|issuer not cooperating|suspended"), 14, False, "Downgrade or negative outlook", "bad"),
        (_t(r"withdraw\w*"), 6, False, "Rating withdrawn", "watch"),  # usually after a repayment, so milder than a downgrade
        (_t(r"upgrad\w*|positive outlook|outlook (?:to|revised to|changed to) positive|watch with positive"), -6, False, "Upgrade", "good"),
        (_t(r"reaffirm\w*|re-affirm\w*|retained|reiterat\w*"), -22, True, "Rating reaffirmed, nothing changed", "neutral"),
    ],
    "pledging": [
        (_t(r"invok\w+|invocation"), 6, False, "Pledge invoked: lenders may sell the shares", "bad"),
        (_t(r"releas\w+|revok\w+|revocation|cessation of (?:the )?(?:pledge|encumbrance)"), -30, False, "Pledge released: good news", "good"),
    ],
    "management_change": [
        (_t(rf"(?:{_EXIT}).{{0,120}}(?:{_KEY_ROLE})|(?:{_KEY_ROLE}).{{0,120}}(?:{_EXIT})"), 12, False, "A key person is leaving: exits rank above hires", "bad"),
        (_t(r"re-?appoint\w*"), -15, False, "Re-appointment of someone already in the role", "neutral"),
        (_t(rf"(?:{_MINOR_ROLE})"), -12, False, "Minor role", "neutral"),
        (_t(r"retire\w*|superannuat\w*"), 2, False, "A planned exit: ranks just above an appointment", "watch"),
        (_t(_EXIT), 6, False, "An exit ranks above an appointment", "watch"),
    ],
    "fund_raise": [
        (_t(r"esop|esps|esos|employee stock|stock options?|options to purchase"), -10, True, "Employee share allotment", "neutral"),
    ],
}

_TRANSCRIPT = _t(r"transcript")
# "Reference to the financial results issued by Suzuki Motor" is about somebody else's results.
_NOT_OWN_RESULTS = _t(r"results (?:issued|published|announced|released|declared) by|reference to the financial results")


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _best_text_match(text: str) -> Classification | None:
    weights = categories()
    best: tuple[int, int, str, Classification] | None = None
    for order, (rule_id, pattern, result) in enumerate(TEXT_RULES):
        if rule_id == "text:results" and _NOT_OWN_RESULTS.search(text):
            continue
        if pattern.search(text):
            key = (weights[result.category].weight, -order)
            if best is None or key > best[:2]:
                best = (key[0], key[1], rule_id, result)
    return replace(best[3], rule=best[2]) if best else None


def _refine(c: Classification, text: str) -> Classification:
    for pattern, adjust, routine, note, tone in REFINERS.get(c.category, []):
        if pattern.search(text):
            return replace(c, adjust=c.adjust + adjust, routine=c.routine or routine, note=note, tone=tone)
    return c


def classify(*, source: str, category: str, subcategory: str = "", subject: str = "", body: str = "") -> Classification:
    """Classify one announcement. `category` and `subcategory` are the exchange's own labels
    (for NSE, `category` is its one-line description and `subcategory` is empty)."""
    cat, sub = _norm(category), _norm(subcategory)
    text = _norm(f"{subject} {body}")
    if source == "nse":
        entry, label = NSE_LABELS.get(cat), f"nse:{cat}"
    else:
        entry, label = BSE_LABELS.get((cat, sub)), f"bse:{cat}/{sub}".rstrip("/")
    if entry is None:
        # A label we have never seen: let its own words take part in the keyword rules.
        text = _norm(f"{cat} {sub} {text}")

    if entry is not None and not entry.read_text:
        chosen = replace(entry.result, rule=label)
    else:
        hit = _best_text_match(text)
        if hit is not None:
            chosen = hit
        elif entry is not None:
            chosen = replace(entry.result, rule=label)
        else:
            chosen = Classification("unclassified", rule="no rule matched")

    # A transcript is a transcript wherever the company filed it.
    if _TRANSCRIPT.search(text) and chosen.category in ("investor_meetings", "earnings_call", "unclassified"):
        return Classification("earnings_call", note="Call transcript", rule="text:transcript")
    return _refine(chosen, text)
