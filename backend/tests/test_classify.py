"""The Tier 0 classifier and the priority score. Cases are real exchange labels and wording unless noted."""
import pytest

from app.push.classify import BSE_LABELS, NSE_LABELS, classify
from app.push.priority import score


def bse(category, sub="", subject="", body=""):
    return classify(source="bse", category=category, subcategory=sub, subject=subject, body=body)


def nse(desc, subject="", body=""):
    return classify(source="nse", category=desc, subcategory="", subject=subject or desc, body=body)


def rank(c):
    return score(c).priority


# ---------- exact labels ----------
@pytest.mark.parametrize(
    "category, sub, expected",
    [
        ("Result", "Financial Results", "results"),
        ("Board Meeting", "Board Meeting", "agm_egm"),
        ("AGM/EGM", "Postal Ballot", "postal_ballot"),
        ("AGM/EGM", "AGM", "agm_egm"),
        ("Insider Trading / SAST", "Closure of Trading Window", "insider_trading"),
        ("Corp. Action", "Dividend", "dividend"),
        ("Corp. Action", "Bonus", "bonus_split"),
        ("Corp. Action", "Sub-division / Stock Split", "bonus_split"),
        ("Corp. Action", "Bonds / Right issue", "fund_raise"),
        (" Corp Action", "Dividend Updates", "dividend"),  # note BSE's leading space in the category
        ("Company Update", "Credit Rating", "credit_rating"),
        ("Company Update", "Acquisition", "m_and_a"),
        ("Company Update", "Change in Management", "management_change"),
        ("Company Update", "Resignation of Chief Financial Officer (CFO)", "management_change"),
        ("Company Update", "Analyst / Investor Meet", "investor_meetings"),
        ("Company Update", "Earnings Call Transcript", "earnings_call"),
        ("Company Update", "Investor Presentation", "investor_meetings"),
        ("Company Update", "Press Release / Media Release", "press_release"),
        ("Company Update", "Qualified Institutional Placement", "fund_raise"),
        ("Company Update", "Intimation of meeting of Committee of Creditors", "litigation"),
        ("Company Update", "Memorandum of Understanding /Agreements", "m_and_a"),
    ],
)
def test_known_bse_labels(category, sub, expected):
    assert bse(category, sub).category == expected


@pytest.mark.parametrize(
    "desc, expected",
    [
        ("Credit Rating- Revision", "credit_rating"),
        ("Pendency of Litigation(s)/dispute(s) or the outcome impacting the Company", "litigation"),
        ("Reasons for Delayed/Non-submission of Financial Results", "litigation"),
        ("Integrated Filing- Financial", "results"),
        ("Resignation of Director/KMP/SMP", "management_change"),
        ("Bagging/Receiving of orders/contracts", "press_release"),
        ("Capacity addition", "capex"),
        ("Stock split", "bonus_split"),
        ("Analysts/Institutional Investor Meet/Con. Call Updates", "investor_meetings"),
    ],
)
def test_known_nse_labels(desc, expected):
    assert nse(desc).category == expected


def test_every_label_points_at_a_real_category():
    from app.push.categories import load

    valid = set(load())
    assert {e.result.category for e in BSE_LABELS.values()} <= valid
    assert {e.result.category for e in NSE_LABELS.values()} <= valid


# ---------- routine versus not ----------
@pytest.mark.parametrize(
    "category, sub",
    [
        ("Company Update", "Newspaper Publication"),
        ("Company Update", "Allotment of ESOP / ESPS"),
        ("Company Update", "Monitoring Agency Report"),
        ("Company Update", "Certificate under Reg. 74 (5) of SEBI (DP) Regulations, 2018"),
        ("Insider Trading / SAST", "Closure of Trading Window"),
        ("Company Update", "Analyst / Investor Meet"),
        ("Others", "Reg. 34 (1) Annual Report"),
    ],
)
def test_routine_filings_are_collapsed(category, sub):
    assert score(bse(category, sub)).routine


@pytest.mark.parametrize(
    "category, sub", [("Result", "Financial Results"), ("Company Update", "Credit Rating"), ("Company Update", "Change in Management")]
)
def test_material_filings_are_not_routine(category, sub):
    assert not score(bse(category, sub)).routine


# ---------- the keyword rules for vague labels ----------
def test_general_filings_are_read_by_their_words():
    c = bse("Company Update", "General", "Update On Ongoing Material Litigation(S) Or Dispute(S)", "details of the matter")
    assert c.category == "litigation" and c.rule == "text:litigation"


def test_an_outcome_of_board_meeting_about_results_is_results():
    c = bse("Board Meeting", "Outcome of Board Meeting", "Board Meeting Outcome for Unaudited Financial Results For The Quarter", "")
    assert c.category == "results"


def test_a_board_outcome_with_no_content_stays_unclassified_but_visible():
    c = bse("Board Meeting", "Outcome of Board Meeting", "Board Meeting Outcome for Outcome Of Board Meeting", "Outcome of Board Meeting")
    s = score(c)
    assert c.category == "unclassified" and not s.routine  # shown, never hidden as routine


def test_the_most_serious_matching_category_wins():
    # Mentions a dividend and a court order; the risk must not be hidden behind the harmless word.
    c = bse("Company Update", "General", "Outcome", "Board declared a dividend; the High Court passed an order against the company")
    assert c.category == "litigation"


def test_a_transcript_is_a_transcript_wherever_it_was_filed():
    c = bse("Company Update", "Analyst / Investor Meet", "Outcome", "Transcript of conference call held in respect of Financial Results")
    assert c.category == "earnings_call"


def test_somebody_elses_results_are_not_this_companys_results():
    # Real Maruti filing: it is about the parent's results, so it must not get the 88-point results rank.
    c = bse("Company Update", "General", "Reference to the Financial Results Issued by Suzuki Motor Corporation", "Please find enclosed")
    assert c.category != "results"


@pytest.mark.parametrize(
    "subject",
    [
        "Unaudited Financial Results For The Quarter And Half Year Ended September 30, 2026",
        "Board Meeting Outcome for Approval of Financial Results for the quarter",
        "Integrated Financial Results (Standalone And Consolidated) and Limited Review Report",
    ],
)
def test_a_boards_own_results_are_still_recognised_from_their_words(subject):
    assert bse("Board Meeting", "Outcome of Board Meeting", subject).category == "results"


def test_a_subsidiarys_voluntary_winding_up_is_not_litigation():
    c = bse("Company Update", "General", "Voluntary Winding Up Of Reliance Neucomm LLC", "Voluntary winding up of the LLC")
    assert c.category != "litigation"


def test_an_unknown_label_still_gets_read_by_its_own_words():
    c = bse("Company Update", "Resignation of Chief Technology Officer", "Intimation", "")
    assert c.category == "management_change"


def test_nothing_recognisable_is_unclassified_not_dropped():
    c = bse("Company Update", "General", "Update To Disclosure Dated June 21, 2022", "Update to disclosure dated June 21, 2022")
    assert c.category == "unclassified" and not score(c).routine


# ---------- negativity bias: bad news outranks good news ----------
def test_a_downgrade_outranks_a_reaffirmation_and_an_upgrade():
    down = bse("Company Update", "Credit Rating", body="CRISIL has downgraded the rating to A from A+")
    up = bse("Company Update", "Credit Rating", body="ICRA has upgraded the rating to AA")
    same = bse("Company Update", "Credit Rating", body="CARE has reaffirmed the rating at AA+")
    assert rank(down) > rank(up) > rank(same)
    assert score(same).routine and not score(down).routine
    assert "Downgrade" in score(down).why


def test_a_withdrawn_rating_is_milder_than_a_downgrade():
    down = bse("Company Update", "Credit Rating", body="Rating downgraded")
    withdrawn = bse("Company Update", "Credit Rating", body="Withdrawal of Credit Rating")
    assert rank(withdrawn) < rank(down)


def test_a_cfo_leaving_outranks_a_cfo_arriving():
    leaves = bse("Company Update", "Change in Management", body="Resignation of Mr. Rao from the position of CFO")
    arrives = bse("Company Update", "Change in Management", body="Appointment of Mr. Rao as CFO and KMP")
    assert rank(leaves) > rank(arrives)
    assert "key person" in score(leaves).why.lower()


def test_re_appointing_someone_already_in_the_role_ranks_below_a_new_hire():
    # A real HDFC Bank filing: the Whole-time Director's re-appointment reached "Needs attention" at 85.
    reappoint = bse("Company Update", "Change in Management", body="Re-appointment of Mr. V. Srinivasa Rangan as Whole-time Director")
    hire = bse("Company Update", "Change in Management", body="Appointment of Mr. Rao as Whole-time Director")
    assert rank(reappoint) < rank(hire)
    assert score(reappoint).tone == "neutral" and 45 <= rank(reappoint) < 75  # worth a look, not urgent


def test_a_key_person_leaving_still_beats_a_re_appointment_in_the_same_filing():
    both = bse("Company Update", "Change in Management", body="Resignation of the CFO and re-appointment of the Chairman")
    assert "key person" in score(both).why.lower()


def test_a_company_secretary_change_is_a_minor_item():
    minor = bse("Company Update", "Resignation of Company Secretary / Compliance Officer")
    cfo = bse("Company Update", "Resignation of Chief Financial Officer (CFO)", body="Resignation of CFO")
    assert rank(minor) < rank(cfo)


def test_pledge_invocation_ranks_above_creation_and_release_ranks_below():
    # No real pledge filing appeared in ~3,500 sampled filings, so these are written wording.
    invoke = bse("Company Update", "General", "Disclosure under SEBI Takeover Regulations", "Lenders have invoked the pledge on 2,000,000 shares of the promoter")
    create = bse("Company Update", "General", "Disclosure under SEBI Takeover Regulations", "Promoter created an encumbrance by pledging 1,000,000 shares")
    release = bse("Company Update", "General", "Disclosure under SEBI Takeover Regulations", "Release of the pledge on 1,000,000 shares")
    assert invoke.category == create.category == release.category == "pledging"
    assert rank(invoke) > rank(create) > rank(release)


def test_the_category_order_puts_risks_first():
    litigation = rank(bse("Company Update", "Intimation of meeting of Committee of Creditors"))
    results = rank(bse("Result", "Financial Results"))
    dividend = rank(bse("Corp. Action", "Dividend"))
    assert litigation > results > dividend


def test_exchange_questions_and_disruptions_are_lifted_above_plain_unclassified():
    plain = rank(bse("Company Update", "General", "Update", "nothing recognisable here"))
    assert rank(nse("Spurt in Volume")) > plain
    assert rank(bse("Company Update", "Strikes /Lockouts / Disturbances")) > plain


# ---------- tone: the only thing the app is allowed to colour ----------
def tone(c):
    return score(c).tone


def test_bad_news_is_bad_and_good_news_is_good():
    assert tone(bse("Company Update", "Credit Rating", body="CRISIL downgraded the rating")) == "bad"
    assert tone(bse("Company Update", "Credit Rating", body="ICRA upgraded the rating")) == "good"
    assert tone(bse("Company Update", "Credit Rating", body="CARE reaffirmed the rating")) == "neutral"
    assert tone(bse("Company Update", "Credit Rating", body="Withdrawal of Credit Rating")) == "watch"
    assert tone(bse("Company Update", "Intimation of meeting of Committee of Creditors")) == "bad"
    assert tone(nse("Pendency of Litigation(s)/dispute(s) or the outcome impacting the Company")) == "bad"
    assert tone(bse("Company Update", "General", "x", "The High Court passed an order against the company")) == "bad"


def test_leadership_exits_are_coloured_by_how_serious_they_are():
    assert tone(bse("Company Update", "Change in Management", body="Resignation of the CFO")) == "bad"
    assert tone(bse("Company Update", "Change in Management", body="Resignation of a senior vice president")) == "watch"
    assert tone(bse("Company Update", "Change in Management", body="Appointment of Mr. Rao as CFO")) == "neutral"


def test_pledges_are_a_watch_item_unless_invoked_or_released():
    pledge = ("Company Update", "General", "Disclosure under SEBI Takeover Regulations")
    assert tone(bse(*pledge, "Promoter created a pledge on 1,000,000 shares")) == "watch"
    assert tone(bse(*pledge, "Lenders have invoked the pledge on 2,000,000 shares")) == "bad"
    assert tone(bse(*pledge, "Release of the pledge on 1,000,000 shares")) == "good"


def test_disruptions_and_exchange_questions_are_watch_items():
    assert tone(bse("Company Update", "Strikes /Lockouts / Disturbances")) == "watch"
    assert tone(nse("Spurt in Volume")) == "watch"


def test_ordinary_filings_and_results_stay_uncoloured_until_the_numbers_are_known():
    assert tone(bse("Result", "Financial Results")) == "neutral"
    assert tone(bse("Corp. Action", "Dividend")) == "neutral"
    assert tone(bse("Company Update", "Newspaper Publication")) == "neutral"


# ---------- scoring ----------
def test_priority_stays_between_0_and_100():
    for entry in [*BSE_LABELS.values(), *NSE_LABELS.values()]:
        assert 0 <= score(entry.result).priority <= 100


def test_the_why_line_explains_the_rank_in_plain_words():
    assert score(bse("Result", "Financial Results")).why == "Quarterly results are the most material filing"
    assert score(bse("Company Update", "Newspaper Publication")).why == "Routine: Newspaper copy of an earlier filing"
    assert score(bse("Insider Trading / SAST", "Closure of Trading Window")).why == "Routine trading disclosure"
    assert score(bse("Company Update", "Strikes /Lockouts / Disturbances")).why.startswith("Operations may be disrupted.")


def test_a_non_independent_director_is_not_mistaken_for_an_independent_one():
    # A real Tata Steel filing: the Vice-Chairman's retirement was labelled "Minor role" because "Non-Independent Director"
    # contains the words "independent director".
    retires = bse("Company Update", "Retirement", body="Retirement of Mr. Noel Naval Tata as Non-Executive, Non-Independent Director and as Vice-Chairman of the Board")
    independent = bse("Company Update", "Change in Management", body="Appointment of Mr. Rao as an Independent Director")
    assert "Minor role" not in score(retires).why and "Minor role" in score(independent).why
    assert score(retires).tone == "watch" and "planned exit" in score(retires).why
    assert rank(retires) > rank(independent)


def test_a_planned_retirement_ranks_below_a_resignation_and_above_an_appointment():
    retire = bse("Company Update", "Change in Management", body="Retirement of Mr. Rao as Whole-time Director")
    resign = bse("Company Update", "Change in Management", body="Resignation of Mr. Rao as Whole-time Director")
    hire = bse("Company Update", "Change in Management", body="Appointment of Mr. Rao as Whole-time Director")
    assert rank(resign) > rank(retire) > rank(hire)


def test_retirement_by_rotation_with_reappointment_is_still_a_reappointment():
    both = bse("Company Update", "Change in Management", body="Mr. Rao retires by rotation and, being eligible, offers himself for re-appointment as Director")
    assert "Re-appointment" in score(both).why
