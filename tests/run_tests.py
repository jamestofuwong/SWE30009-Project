#!/usr/bin/env python3
"""Selenium functional tests for the AI Gateway usage calculator.

Reads test cases from test_cases.csv, drives the app in a real browser, compares the
Summary panel against the expected values and prints PASS/FAIL per test case.

    python run_tests.py                              # http://localhost:5173, visible Chrome
    python run_tests.py --headless
    python run_tests.py --url http://localhost:8787  # also works against the vanilla version
"""
import argparse
import csv
import json
import platform
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

CSV_PATH = Path(__file__).with_name("test_cases.csv")
REPORT_DIR = Path(__file__).with_name("report")  # results.json + screenshots go here
SUMMARY = "section[aria-labelledby='sum-h']"
TIMEOUT = 10


# a) read the test cases from the csv file
def read_test_cases(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# b) launch a browser instance
def launch_browser(headless):
    opts = webdriver.ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")  # needed on CI runners
        opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,900")
    return webdriver.Chrome(options=opts)  # Selenium Manager fetches the driver


def parse_usage(text):
    """'a=1;b=2.5' -> [('a', '1'), ('b', '2.5')]"""
    return [tuple(p.split("=", 1)) for p in text.split(";") if p]


def normalise_money(text):
    return text.replace("−", "").replace("-", "").strip()  # discount is shown as "−$x"


# d) feed a test case into the app and click the calculate button
def run_case(driver, wait, url, case):
    driver.get(url)  # c) navigate to the web application
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type=number]")))  # models loaded

    if case["batch"].strip().lower() == "true":
        driver.find_element(By.CSS_SELECTOR, "label.toggle").click()
    for model_id, tokens in parse_usage(case["usage"]):
        field = driver.find_element(By.ID, model_id)
        field.clear()
        field.send_keys(tokens)

    driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
    # Wait for the app to respond with either a result or a validation message.
    wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, f"{SUMMARY} .totals, {SUMMARY} .notice.warn"))

    if case["after_calculate"] == "toggle_batch":
        driver.find_element(By.CSS_SELECTOR, "label.toggle").click()
        wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, f"{SUMMARY} .notice.stale"))

    return read_summary(driver)


def read_summary(driver):
    """Scrape the Summary panel into a dict keyed like the csv's expected_* columns."""
    s = {
        "lines": len(driver.find_elements(By.CSS_SELECTOR, f"{SUMMARY} .line")),
        "list": None, "discount": None, "subtotal": None, "sst": None, "total": None,
    }
    for row in driver.find_elements(By.CSS_SELECTOR, f"{SUMMARY} .totals > div"):
        label = row.find_element(By.CSS_SELECTOR, "dt").text.strip()
        value = normalise_money(row.find_element(By.CSS_SELECTOR, "dd").text)
        key = {"List price": "list", "Subtotal": "subtotal", "Total to pay": "total"}.get(label)
        if label.startswith("Batch discount"):
            key = "discount"
        elif label.startswith("SST"):
            key = "sst"
        if key:
            s[key] = value
    notices = driver.find_elements(By.CSS_SELECTOR, f"{SUMMARY} .notice")
    s["notice"] = " | ".join(n.text.strip().lstrip("! ").strip() for n in notices)
    return s


# e) compare actual against expected
def compare(case, actual):
    failures = []
    expected_lines = int(case["expected_lines"])
    if actual["lines"] != expected_lines:
        failures.append(f"line items: expected {expected_lines}, got {actual['lines']}")
    for key in ("list", "discount", "subtotal", "sst", "total"):
        expected = case[f"expected_{key}"].strip() or None  # blank = row must be absent
        if actual[key] != expected:
            failures.append(f"{key}: expected {expected}, got {actual[key]}")
    expected_notice = case["expected_notice"].strip()
    if expected_notice and expected_notice not in actual["notice"]:
        failures.append(f"notice: expected '{expected_notice}', got '{actual['notice']}'")
    if not expected_notice and actual["notice"]:
        failures.append(f"unexpected notice: '{actual['notice']}'")
    return failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:5173")
    ap.add_argument("--csv", default=str(CSV_PATH))
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--report-dir", default=str(REPORT_DIR), help="where to write results.json and screenshots")
    args = ap.parse_args()

    try:
        urllib.request.urlopen(args.url, timeout=5)
    except OSError:
        sys.exit(f"Cannot reach {args.url} - start the app first with `npm run dev`.")

    report_dir = Path(args.report_dir)
    (report_dir / "screenshots").mkdir(parents=True, exist_ok=True)

    cases = read_test_cases(args.csv)
    driver = launch_browser(args.headless)
    wait = WebDriverWait(driver, TIMEOUT)
    results = []
    started = datetime.now(timezone.utc)
    run_start = time.perf_counter()
    try:
        # g) repeat c) - f) for every test case
        for case in cases:
            actual = None
            t0 = time.perf_counter()
            try:
                actual = run_case(driver, wait, args.url, case)
                failures = compare(case, actual)
            except TimeoutException:
                failures = ["timed out waiting for the app to respond"]
            except Exception as e:  # keep going so one broken case doesn't hide the rest
                failures = [f"{type(e).__name__}: {e}".splitlines()[0]]
            duration = time.perf_counter() - t0

            # Keep a screenshot of the final page state for the report.
            shot = f"screenshots/{case['test_id']}.png"
            try:
                driver.save_screenshot(str(report_dir / shot))
            except Exception:
                shot = None

            # f) display pass/fail
            status = "PASS" if not failures else "FAIL"
            print(f"[{status}] {case['test_id']} - {case['description']} ({duration:.2f}s)")
            for f in failures:
                print(f"         - {f}")
            results.append({
                "id": case["test_id"], "description": case["description"], "status": status,
                "duration": round(duration, 3), "failures": failures,
                "case": case, "actual": actual, "screenshot": shot,
            })
        caps = driver.capabilities
        browser = f"{caps.get('browserName', 'chrome')} {caps.get('browserVersion', '')}".strip()
        driver_version = caps.get("chrome", {}).get("chromedriverVersion", "").split(" ")[0]
    finally:
        driver.quit()

    passed = sum(r["status"] == "PASS" for r in results)
    print(f"\n{passed}/{len(results)} test cases passed")

    (report_dir / "results.json").write_text(json.dumps({
        "url": args.url,
        "started": started.isoformat(timespec="seconds"),
        "total_duration": round(time.perf_counter() - run_start, 3),
        "environment": {
            "os": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
            "browser": browser,
            "chromedriver": driver_version,
            "headless": args.headless,
        },
        "results": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
