from cryptobot.desk import dash_hosts


def test_dash_hosts_merges_flags_and_env():
    assert dash_hosts(None, {}) == set()
    assert dash_hosts(["Desk.Example.TS.NET"], {}) == {"desk.example.ts.net"}
    env = {"CRYPTOBOT_DASH_HOSTS": " desk.tail1234.ts.net, 100.64.0.5 ,"}
    assert dash_hosts(["lan"], env) == {"lan", "desk.tail1234.ts.net", "100.64.0.5"}
    assert dash_hosts([], {"CRYPTOBOT_DASH_HOSTS": ""}) == set()
