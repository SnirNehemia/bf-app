"""
Smoke test for the feeding tracker.

Serves the repo over http on localhost (a secure origin, so the service worker and Chrome's install
checks run) and drives the app in a headless Chromium at a Galaxy S25-sized viewport, in Hebrew.

Run from the repo root:
    pip install playwright && playwright install chromium     (once)
    python3 tests/smoke_test.py

Exit code 0 = all checks passed.
"""
import functools
import http.server
import pathlib
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright

REPO_DIR = pathlib.Path(__file__).resolve().parent.parent
MS_MINUTE = 60_000
STORAGE_PREFIX = "feedingTracker.v1."

failures = []


def check(condition, description):
    print(("ok    " if condition else "FAIL  ") + description)
    if not condition:
        failures.append(description)


def start_static_server():
    """Serves the repo folder on a free local port; returns (server, base_url)."""
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):  # keep the test output readable
            pass

    handler = functools.partial(QuietHandler, directory=str(REPO_DIR))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/"


def dismiss_surprise(page):
    """Surprise cards (milestones, morning message) can appear after saving; close them so taps reach the app."""
    if page.is_visible("#moment"):
        page.tap('[data-action="close-moment"]')
        page.wait_for_timeout(100)


def age_running_feed(page, milliseconds):
    """Pretend the running feed started `milliseconds` earlier (so tests need not wait minutes)."""
    page.evaluate("""(ms) => {
        const session = appState.activeSession;
        session.startMs -= ms;
        session.segments.forEach(segment => { segment.startMs -= ms; if (segment.endMs) segment.endMs -= ms; });
        saveActiveSession(); renderAll();
    }""", milliseconds)


def age_last_saved_feed(page, milliseconds):
    """Pretend the last saved feed ended `milliseconds` earlier."""
    page.evaluate("""(ms) => {
        const entry = appState.entries[appState.entries.length - 1];
        entry.startMs -= ms; entry.endMs -= ms;
        entry.segments.forEach(segment => { segment.startMs -= ms; segment.endMs -= ms; });
        saveEntries(); renderAll();
    }""", milliseconds)


def run(base_url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            viewport={"width": 412, "height": 915}, device_scale_factor=2, is_mobile=True, has_touch=True,
            locale="he-IL", timezone_id="Asia/Jerusalem", accept_downloads=True,
        )
        page = context.new_page()
        page.on("pageerror", lambda error: failures.append(f"page error: {error}"))
        page.on("dialog", lambda dialog: dialog.accept())
        page.goto(base_url)
        page.evaluate("localStorage.clear()")
        page.reload()
        page.wait_for_timeout(400)

        # ---- first run: asks for the baby's name once
        check(page.evaluate("document.getElementById('sheet').open"), "first launch asks for the name")
        check(page.inner_text(".app-title") == "יומן", "title is generic before a name is set")
        page.fill('input[name="babyName"]', "נועה")
        page.tap('form[data-form="name"] button[type="submit"]')
        page.wait_for_timeout(300)
        check(page.inner_text(".app-title") == "נועה", "title shows the typed name")

        # ---- a feed: start right, switch to left, finish
        page.tap('.dial[data-side="R"]')
        age_running_feed(page, 9 * MS_MINUTE)
        page.tap('.dial[data-side="L"]')
        age_running_feed(page, 4 * MS_MINUTE)
        page.tap('[data-action="finish"]')
        page.wait_for_timeout(200)
        dismiss_surprise(page)
        saved = page.evaluate(f"JSON.parse(localStorage.getItem('{STORAGE_PREFIX}entries'))")
        check(len(saved) == 1 and [s["side"] for s in saved[0]["segments"]] == ["R", "L"], "feed saved with both sides in order")
        original_start_ms = saved[0]["startMs"]
        check(page.get_attribute(".dial.is-suggested", "data-side") == "L", "suggestion: the side she finished on (both sides used)")

        # ---- resume the saved feed (baby cried for more)
        check(page.is_visible('[data-live="resume-card"]'), "resume card is offered right after saving")
        check("בשמאל" in page.inner_text('[data-action="resume-last"]'), "resume button names the side she finished on")
        total_before_ms = page.evaluate("totalFeedingMs(appState.entries[0].segments)")
        page.tap('[data-action="resume-last"]')
        page.wait_for_timeout(300)
        session = page.evaluate("appState.activeSession")
        check(session is not None and session["startMs"] == original_start_ms, "resumed feed keeps its original start time")
        check(page.evaluate("appState.entries.length") == 0, "saved entry is removed while it runs again")
        check(len(session["segments"]) == 3 and session["segments"][-1]["endMs"] is None and session["segments"][-1]["side"] == "L",
              "new running segment on the side she finished on")
        page.evaluate("() => { const s = appState.activeSession; const open = s.segments[s.segments.length-1]; open.startMs -= 3*60000; saveActiveSession(); renderAll(); }")
        page.reload()
        page.wait_for_timeout(300)
        check(page.evaluate("appState.activeSession !== null"), "resumed feed survives a reload")
        page.tap('[data-action="finish"]')
        page.wait_for_timeout(200)
        dismiss_surprise(page)
        resumed = page.evaluate("appState.entries")
        check(len(resumed) == 1 and len(resumed[0]["segments"]) == 3 and resumed[0]["startMs"] == original_start_ms,
              "finishing saves ONE feed with the earlier and new parts")
        total_after_ms = page.evaluate("totalFeedingMs(appState.entries[0].segments)")
        check(2.5 * MS_MINUTE < total_after_ms - total_before_ms < 4 * MS_MINUTE, "only feeding time is added (the gap is not counted)")

        # ---- resume is only offered for 30 minutes, and not during a running feed
        age_last_saved_feed(page, 31 * MS_MINUTE)
        check(not page.is_visible('[data-live="resume-card"]') if page.query_selector('[data-live="resume-card"]') else True,
              "no resume card 31 minutes after the feed ended")
        page.tap('.dial[data-side="R"]')
        check(page.evaluate("findResumableFeed(Date.now())") is None, "nothing to resume while a feed is running")
        page.tap('[data-action="discard"]')
        page.wait_for_timeout(200)

        # ---- bottle
        page.tap('[data-action="open-bottle"]')
        page.wait_for_timeout(250)
        page.tap('[data-action="set-volume"][data-value="90"]')
        page.tap('#bottle-form button[type="submit"]')
        page.wait_for_timeout(250)
        check(page.evaluate("appState.entries.some(e => e.type === 'bottle' && e.volumeMl === 90)"), "bottle saved")

        # ---- solid food meal
        page.tap('[data-action="go-tab"][data-tab="food"]')
        page.tap('.food-header [data-action="open-meal"]')
        page.wait_for_timeout(250)
        page.tap('.sheet [data-action="toggle-food"][data-food="אבוקדו"]')
        page.tap('#meal-form button[type="submit"]')
        page.wait_for_timeout(700)
        dismiss_surprise(page)
        check(page.evaluate("appState.meals.length") == 1, "meal saved")

        # ---- backup round trip keeps feeds, meals and the name
        page.tap('[data-action="open-backup"]')
        page.wait_for_timeout(250)
        with page.expect_download() as download:
            page.tap('[data-action="export-json"]')
        backup_path = pathlib.Path(tempfile.mkdtemp()) / "backup.json"
        download.value.save_as(str(backup_path))
        page.evaluate("localStorage.clear()")
        page.evaluate(f"localStorage.setItem('{STORAGE_PREFIX}nameAsked', 'true')")
        page.reload()
        page.wait_for_timeout(300)
        page.set_input_files("#import-file-input", str(backup_path))
        page.wait_for_timeout(500)
        check(page.evaluate("appState.entries.length") == 2 and page.evaluate("appState.meals.length") == 1, "backup restores feeds and meals")
        check(page.inner_text(".app-title") == "נועה", "backup restores the name")

        # ---- installable and offline
        page.wait_for_timeout(1200)
        check(page.evaluate("navigator.serviceWorker.getRegistration().then(r => Boolean(r && r.active))"), "service worker is active")
        cdp = context.new_cdp_session(page)
        install_errors = cdp.send("Page.getInstallabilityErrors").get("installabilityErrors")
        check(install_errors == [], f"Chrome finds no install problems {install_errors if install_errors else ''}")
        context.set_offline(True)
        page.goto(base_url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(600)
        check(page.inner_text(".app-title") == "נועה", "app opens offline")
        fonts_ready = page.evaluate("document.fonts.ready.then(() => document.fonts.check('16px \"Rubik Embedded\"', 'שלום'))")
        check(fonts_ready, "embedded font loads offline")
        browser.close()


server, url = start_static_server()
try:
    run(url)
finally:
    server.shutdown()

print("\nFAILED:" if failures else "\nall checks passed", *failures, sep="\n")
sys.exit(1 if failures else 0)
