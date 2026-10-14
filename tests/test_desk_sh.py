"""desk.sh: the phone-friendly control script, exercised without Docker."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo(tmp_path):
    for f in ("desk.sh", ".env.example", "cryptobot_config.yaml"):
        shutil.copy(ROOT / f, tmp_path / f)
    (tmp_path / "desk.sh").chmod(0o755)
    return tmp_path


def run(repo, *args, stdin=""):
    env = {**os.environ, "PATH": "/usr/bin:/bin", "USER": "me"}      # no docker on PATH
    return subprocess.run(["bash", "./desk.sh", *args], cwd=repo, input=stdin, text=True,
                          capture_output=True, env=env, timeout=60)


def env_of(repo):
    return dict(line.split("=", 1) for line in (repo / ".env").read_text().splitlines()
                if "=" in line and not line.startswith("#"))


def test_keys_writes_env_with_mode_600_and_keeps_blank_answers(repo):
    pem = "-----BEGIN PRIVATE KEY-----\nabc\ndef\n-----END PRIVATE KEY-----\n"
    answers = "kid-123\n" + pem + "AKPAPER\nsecret1\n\n\n\n\n\n"
    r = run(repo, "keys", stdin=answers)
    assert r.returncode == 0, r.stderr
    e = env_of(repo)
    assert e["CRYPTOBOT_KALSHI_KEY_ID"] == "kid-123"
    assert e["CRYPTOBOT_KALSHI_KEY_PEM"] == "-----BEGIN PRIVATE KEY-----\\nabc\\ndef\\n-----END PRIVATE KEY-----"
    assert e["CRYPTOBOT_ALPACA_KEY_ID"] == "AKPAPER" and e["CRYPTOBOT_ALPACA_SECRET_KEY"] == "secret1"
    assert e["CRYPTOBOT_ALERT_WEBHOOK"] == "" and e["CRYPTOBOT_DASH_TOKEN"] not in ("", "change-me-to-a-long-random-string")
    assert oct((repo / ".env").stat().st_mode & 0o777) == "0o600"
    # a second run with blank answers changes nothing
    before = (repo / ".env").read_text()
    assert run(repo, "keys", stdin="\n" * 12).returncode == 0
    assert (repo / ".env").read_text() == before


def test_pem_from_a_file_and_one_line_form(repo):
    pem_file = repo / "k.pem"
    pem_file.write_text("-----BEGIN PRIVATE KEY-----\nxyz\n-----END PRIVATE KEY-----\n")
    assert run(repo, "keys", stdin=f"kid\n{pem_file}\n" + "\n" * 10).returncode == 0
    assert env_of(repo)["CRYPTOBOT_KALSHI_KEY_PEM"] == "-----BEGIN PRIVATE KEY-----\\nxyz\\n-----END PRIVATE KEY-----\\n"
    assert run(repo, "keys", stdin="kid\n-----BEGIN PRIVATE KEY-----\\nq\\n-----END PRIVATE KEY-----\n" + "\n" * 10).returncode == 0
    assert env_of(repo)["CRYPTOBOT_KALSHI_KEY_PEM"] == "-----BEGIN PRIVATE KEY-----\\nq\\n-----END PRIVATE KEY-----"


def test_arm_needs_a_key_then_flips_config_and_env_and_disarm_reverts(repo):
    r = run(repo, "arm")
    assert r.returncode == 1 and "run ./desk.sh keys" in r.stdout
    run(repo, "keys", stdin="kid\n-----BEGIN PRIVATE KEY-----\\na\\n-----END PRIVATE KEY-----\n" + "\n" * 10)
    r = run(repo, "arm")
    assert r.returncode == 0, r.stderr
    cfg = (repo / "cryptobot_config.yaml").read_text()
    perp_block = cfg[cfg.index("\nperp:"):]
    assert "  live: true" in perp_block.split("\ncarry:")[0]
    assert "execution:\n  live: false" in cfg                       # the on-chain block is untouched
    assert env_of(repo)["CRYPTOBOT_ARM_LIVE"] == "yes"
    r = run(repo, "disarm")
    assert r.returncode == 0
    cfg = (repo / "cryptobot_config.yaml").read_text()
    assert "  live: false" in cfg[cfg.index("\nperp:"):].split("\ncarry:")[0]
    assert env_of(repo)["CRYPTOBOT_ARM_LIVE"] == ""


def test_status_and_tunnel_print_the_url_without_docker(repo):
    r = run(repo, "status")
    assert r.returncode == 0 and "http://localhost:8080/?t=" in r.stdout and "docker is not installed" in r.stdout
    assert "armed: perp.live=false" in r.stdout
    t = run(repo, "tunnel")
    assert "Port Forwarding" in t.stdout and "?t=" in t.stdout
    assert "status" in run(repo).stdout                              # usage


def test_config_yaml_still_parses_after_arm(repo):
    import yaml
    run(repo, "keys", stdin="kid\n-----BEGIN PRIVATE KEY-----\\na\\n-----END PRIVATE KEY-----\n" + "\n" * 10)
    run(repo, "arm")
    cfg = yaml.safe_load((repo / "cryptobot_config.yaml").read_text())
    assert cfg["perp"]["live"] is True and cfg["execution"]["live"] is False and cfg["carry"]["live"] is False
