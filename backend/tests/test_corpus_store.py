"""Saving a company's documents with the app, and reading them back without the exchanges."""
import gzip
import json
from datetime import date, datetime

import pytest

from app.core.timeutil import IST
from app.pull import corpus_store as cs
from app.pull import ingest as ig
from app.sources.models import Announcement, Listing
from tests.pdfs import make_transcript_pdf

CORPUS = ig.Corpus(
    symbol="ACME", name="Acme Ltd",
    documents=[
        ig.Document(id="d1", kind="transcript", title="Q1 FY27 earnings call transcript", period="Q1 FY27", date="2026-08-08", url="https://www.bseindia.com/a.pdf", bytes=123, sha256="a" * 64, pages=["page one \u20b9 text", "page two"]),
        ig.Document(id="d2", kind="annual_report", title="Annual report FY26", period="FY26", date="2026-07-31", url="https://www.bseindia.com/b.pdf", bytes=456, sha256="b" * 64, pages=["x"] * 3),
    ],
    warnings=["Only 1 concall transcript was found in the last 14 months, not 4."],
)


def test_a_corpus_comes_back_exactly_as_it_was_saved(tmp_path):
    path = cs.save(CORPUS, tmp_path / "nested")
    assert path.name == "ACME.json.gz" and path.exists()
    assert cs.load("ACME", tmp_path / "nested") == CORPUS


def test_the_same_corpus_gives_the_same_bytes_so_a_rerun_does_not_churn_the_repository(tmp_path):
    first = cs.save(CORPUS, tmp_path).read_bytes()
    assert cs.save(CORPUS, tmp_path).read_bytes() == first


def test_nothing_saved_a_damaged_file_or_a_newer_layout_is_simply_not_there(tmp_path):
    assert cs.load("NOPE", tmp_path) is None
    (tmp_path / "BAD.json.gz").write_bytes(b"not gzip at all")
    assert cs.load("BAD", tmp_path) is None
    (tmp_path / "NEW.json.gz").write_bytes(gzip.compress(json.dumps({"schema": 99}).encode()))
    assert cs.load("NEW", tmp_path) is None
    (tmp_path / "HOLE.json.gz").write_bytes(gzip.compress(json.dumps({"schema": 1, "symbol": "HOLE"}).encode()))
    assert cs.load("HOLE", tmp_path) is None  # missing fields: treated as absent, never a crash


def test_no_temporary_file_is_left_behind(tmp_path):
    cs.save(CORPUS, tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["ACME.json.gz"]


def test_ingest_prefers_the_saved_copy_and_never_calls_the_exchanges(tmp_path):
    cs.save(CORPUS, tmp_path)
    boom = lambda *a, **k: (_ for _ in ()).throw(AssertionError("the exchanges must not be called"))
    s = ig.IngestSources(resolve=boom, bse_announcements=boom, nse_announcements=boom, pdf=boom, corpus_dir=tmp_path)
    steps = []
    assert ig.ingest("ACME", s, progress=steps.append) == CORPUS and steps == ["Reading the saved documents"]


def test_without_a_saved_copy_ingest_goes_to_the_exchanges_as_before(tmp_path):
    listing = Listing("ACME", "Acme Ltd", "INE000000001", "500325", "1")
    a = Announcement("bse", "q", "Acme Ltd", "500325", "Company Update", "Earnings Call Transcript", "Q1 FY27 earnings call transcript", "", datetime(2026, 8, 8, tzinfo=IST), "https://www.bseindia.com/q.pdf", 1)
    pdf = make_transcript_pdf([f"Q1 page {n}\nManagement: we will commission the plant by Q3 FY27, targeting 500 MW of capacity." for n in range(3)])
    s = ig.IngestSources(resolve=lambda sym: listing, bse_announcements=lambda c, x, y: [a], nse_announcements=lambda *a: [], pdf=lambda u: pdf, today=lambda: date(2026, 11, 15), corpus_dir=tmp_path)
    assert [d.period for d in ig.ingest("ACME", s).documents] == ["Q1 FY27"]
