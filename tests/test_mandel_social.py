"""Tests for the social layer's parsing, ticker extraction, lexicon and aggregation (no network)."""

from mandel.data.social import derive, extract_tickers, lexicon_sentiment, parse_reddit_atom, strip_html

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>r/wallstreetbets</title>
<entry><author><name>/u/alpha</name></author><category term="wallstreetbets" label="r/wallstreetbets"/>
<content type="html">&lt;p&gt;Loaded $GME calls, we ride at dawn 🚀&lt;/p&gt;</content><id>t3_1</id>
<link href="https://www.reddit.com/r/wallstreetbets/comments/1/"/><published>2026-10-14T09:00:00+00:00</published>
<updated>2026-10-14T09:05:00+00:00</updated><title>GME to the moon</title></entry>
<entry><author><name>/u/beta</name></author><content type="html">puts on TSLA, this thing will crash</content><id>t3_2</id>
<link href="https://www.reddit.com/r/wallstreetbets/comments/2/"/><updated>2026-10-14T10:00:00+00:00</updated><title>bearish on TSLA</title></entry>
</feed>"""


def test_parse_atom_and_strip():
    posts = parse_reddit_atom(ATOM, "wallstreetbets")
    assert len(posts) == 2
    assert posts[0]["author"] == "/u/alpha" and posts[0]["flair"] == "r/wallstreetbets"
    assert posts[0]["text"] == "Loaded $GME calls, we ride at dawn 🚀"
    assert posts[1]["published"] == "2026-10-14T10:00:00+00:00"       # falls back to updated
    assert strip_html("&lt;b&gt;x&lt;/b&gt; &amp; y") == "x & y"


def test_tickers_and_lexicon():
    assert extract_tickers("Loaded $GME calls and $tsla puts") == {"GME", "TSLA"}
    assert extract_tickers("I think NVDA and IT are fine", known={"NVDA", "IT"}) == {"NVDA"}   # IT is a stop word
    assert extract_tickers("$A $THE") == set()
    s = lexicon_sentiment("Loaded calls, we ride at dawn 🚀 moon")
    assert s["pos"] >= 3 and s["neg"] == 0 and s["score"] == 1.0
    assert lexicon_sentiment("puts on this, it will crash and dump")["score"] == -1.0
    assert lexicon_sentiment("nothing here")["score"] == 0.0


def test_derive_aggregates_by_source_ticker_day():
    posts = parse_reddit_atom(ATOM, "wallstreetbets")
    st = [{"id": 1, "created_at": "2026-10-14T11:00:00Z", "body": "$GME squeeze incoming", "user": "u1", "symbols": ["GME"], "sentiment": "Bullish"},
          {"id": 2, "created_at": "2026-10-14T11:30:00Z", "body": "selling GME", "user": "u2", "symbols": ["GME"], "sentiment": None}]
    rows = derive(posts, st, known={"GME", "TSLA"})
    by = {(r["source"], r["ticker"]): r for r in rows}
    assert by[("reddit", "GME")]["mentions"] == 1 and by[("reddit", "GME")]["bullish"] == 1
    assert by[("reddit", "TSLA")]["bearish"] == 1
    assert by[("stocktwits", "GME")]["mentions"] == 2 and by[("stocktwits", "GME")]["bullish"] == 1 and by[("stocktwits", "GME")]["bearish"] == 1
    assert by[("stocktwits", "GME")]["unique_authors"] == 2 and rows[0]["day"] == "2026-10-14"
