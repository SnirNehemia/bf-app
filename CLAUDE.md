# Feeding tracker

A small offline web app (Hebrew, right-to-left) for logging a baby's breastfeeds and first solid foods.
It is used one-handed, half asleep, at 3am, on an Android phone (Galaxy S25, Chrome, installed as an app).
Everything is stored on the phone; there is no server, account, or network call.

The live site is this repo's `main` branch served by GitHub Pages. **Every commit on `main` reaches the
phone the next time the app is opened.** Treat `main` as production.

## Files

- `index.html` – the whole app: CSS, HTML shell and JavaScript in one file. **Edited directly, no build step.**
  The script is split into numbered banner sections (configuration, storage, state, domain logic, actions,
  insights, rendering, charts, sheets, backup, food, moments, events, start). Find things by those banners.
- `sw.js` – service worker (offline + updates). See "Releasing".
- `manifest.webmanifest`, `icon-*.png` – install-as-app metadata and icons.
- `fonts/` – Rubik (OFL), two woff2 subsets, so the page works offline. Do not load fonts from a CDN.
- `tests/smoke_test.py` – browser test of the main flows (see "Testing").
- `.nojekyll` – tells GitHub Pages to serve the files as they are.

## Working on it

- Run locally: `python3 -m http.server 8000`, then open `http://localhost:8000` (use localhost, not `file://`,
  or the service worker and install checks do not run). Use Chrome DevTools device mode at 412×915.
- Do not add frameworks, bundlers, npm packages, CDN links, analytics or any network request.
  The app must keep working with no connection. A new dependency is almost never the right answer here.
- Code style: heavily commented (explain *why*), explicit descriptive variable names, small modular functions,
  named constants instead of magic numbers (see the constants at the top of the script).

## Testing

`python3 tests/smoke_test.py` serves the repo on a free port and drives the app in headless Chromium
(needs `pip install playwright && playwright install chromium`, once). It covers first-run name, a feed with a side
switch, resuming a saved feed, bottle, solid-food meal, backup and restore, service worker, installability and
offline loading. Run it before every merge to `main`. Add a check for every new behaviour or bug fix.
It must exit 0.

Also look at any UI change yourself: screenshot at 412×915 in **both** light and dark mode
(`color_scheme` in Playwright, or DevTools rendering emulation) and check RTL, text overflow and tap targets.

## Releasing

1. Work on a branch; merge to `main` only after the smoke test passes and you have looked at the screens.
2. Bump `APP_VERSION` in `index.html` **and** `APP_VERSION` in `sw.js` to the same new number
   (it is shown in the app's settings so a phone's version can be checked, and it renames the offline cache).
3. If you add, rename or remove a file the app needs, update `APP_FILES` in `sw.js`.
4. After the merge, GitHub Pages publishes in about a minute. Installed phones update on their next open
   while online; users do not reinstall. Their data is untouched by updates.
   Changes to the icon or app name in the manifest can take Android a day or so to pick up.

## Data safety (the most important rules)

Her logs are irreplaceable (nobody can re-feed a baby to regenerate them) and live only in the phone's `localStorage`.

- Keys are `feedingTracker.v1.*` (entries, meals, activeSession, babyName, momentsSeen, insightsRangeDays,
  lastBackupMs, nameAsked). Never rename a key and never change the shape of a stored object without a
  migration that keeps old data readable. Old backups must keep importing.
- Data is validated on load (`isValidEntry`, `isValidMeal`, `isValidActiveSession`); a bad record is skipped,
  never allowed to break rendering.
- Anything that moves data between states (finishing a feed, resuming one, importing, deleting) must write the
  new state before removing the old one, so an interruption cannot lose a feed.
- The backup file (JSON) is the user's only safety net. Keep export/import working and covered by a test.

## Product behaviour that is deliberate

- Entry types: `breast` (segments per side with start and end times), `bottle` (ml only), plus `meals` for solids.
- Next-side suggestion: start on the side opposite to where the last feed *started*. A side used under 30 seconds
  counts as a mis-tap and is ignored.
- A saved feed can be resumed for 30 minutes (`RESUME_WINDOW_MS`): it reopens as a running feed with its original
  start and earlier segments, continues on the side she finished on, and the time in between is not counted.
- Feeds under 5 seconds are discarded; finishing shows a 7-second undo.
- Solid foods: the app tracks which of the 8 common allergens were introduced and warns gently when a new
  allergen follows another within 3 days or when two are introduced at once. It records and informs; it must
  never give medical advice or tell her what to feed.
- The small surprises ("moments": morning message after a night, milestones, five taps on the title) are
  intentional. Keep them warm, rare and dismissible, and never block a feed.
- The baby's name is typed on the phone and stored locally.

## UI and copy rules

- Hebrew, RTL, plain everyday words, sentence case. A button says what it does and keeps the same name in the
  confirmation ("שמירה" then "נשמר"). Errors say what is wrong and how to fix it, never apologise.
  The tone is calm and kind; no exclamation-heavy cheerleading in routine screens.
- Colours are CSS variables at the top of the stylesheet, with a separate dark set that follows the phone's setting.
  Right side = amber, left side = blue; a side is never shown by colour alone (its name is always written).
  Do not introduce new hard-coded colours.
- Tap targets at least 44px, one-handed reach, readable in a dark room (no pure white on black, no glare).
- Respect `prefers-reduced-motion`. Motion only in response to a tap, except the rare surprises.
- Numbers use tabular figures; clock times are 24-hour (`14:05`); dates are day.month.

## Privacy

This repo is public. Never commit a real name, real feeding data, backup files, screenshots of real data,
phone numbers or addresses. Test data is invented. The baby's name must never appear in any file here.
