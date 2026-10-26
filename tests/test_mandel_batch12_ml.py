"""Batch 12 (learning program) harness wrappers."""


def test_cli_imports_without_pandas():
    """The Linode capture box has numpy but no pandas, scipy or scikit-learn. mandel.ml needs pandas; the runner imports batch12_ml; the CLI imports
    the runner. From 2026-10-21 to 10-23 every nightly options-fetch died at `import pandas` (daily.jsonl rc 1). The ML
    imports are lazy now; this pins it."""
    import subprocess
    import sys
    code = ("import sys\nfor m in ('pandas', 'scipy', 'sklearn', 'statsmodels', 'pyarrow'): sys.modules[m] = None\n"
            "import mandel.cli; import mandel.experiments.run; print('ok')")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120, check=False)
    assert r.returncode == 0 and r.stdout.strip() == "ok", r.stderr[-800:]
