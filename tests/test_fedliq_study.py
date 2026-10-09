import datetime as dt

from cryptobot import fedliq_study as FL


def test_rows_align_h41_wednesday_to_friday_close_and_forward_returns(tmp_path):
    (tmp_path / "WALCL.csv").write_text("observation_date,WALCL\n" + "\n".join(
        f"{dt.date(2024, 1, 3) + dt.timedelta(days=7 * i)},{7_000_000 + 10_000 * i}" for i in range(20)))
    (tmp_path / "WTREGEN.csv").write_text("observation_date,WTREGEN\n" + "\n".join(
        f"{dt.date(2024, 1, 3) + dt.timedelta(days=7 * i)},700000" for i in range(20)))
    (tmp_path / "RRPONTSYD.csv").write_text("observation_date,RRPONTSYD\n" + "\n".join(
        f"{dt.date(2024, 1, 3) + dt.timedelta(days=7 * i)},{500 - 20 * i}" for i in range(20)))
    days = [dt.date(2024, 1, 1) + dt.timedelta(days=i) for i in range(200)]
    (tmp_path / "SP500.csv").write_text("observation_date,SP500\n" + "\n".join(
        f"{d},{4000 + i}" for i, d in enumerate(days) if d.weekday() < 5))
    rows = FL.build_rows(tmp_path)
    assert rows and rows[0]["date"] == dt.date(2024, 1, 31)                  # needs four prior weeks
    r = rows[0]
    nl = (7_040_000 - 700_000 - 420 * 1000)
    assert abs(r["nl"] - nl) < 1 and r["d1"] > 0 and r["d4"] > 0
    assert r["r1"] > 0 and r["r4"] > r["r1"]                                 # rising index
    c = FL.conditional(rows, "d1", "r1")
    assert c["up"]["n"] == len(rows) and c["down"]["n"] == 0
    assert "H.4.1 weeks" in FL.render(rows)
