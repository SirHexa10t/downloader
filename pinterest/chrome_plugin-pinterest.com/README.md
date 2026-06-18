# Pinterest image downloader

A one-click Chrome extension that downloads every full-size image from a
Pinterest **board**, **search results** page, or **pin**.

Open one of those pages → click the toolbar icon → all images save to a
deterministic subfolder of `Downloads/Pinterest/`:

| Page | Example | Saves to |
|---|---|---|
| Board | `pinterest.com/<user>/<board>/` | `Pinterest/<board-name>/` |
| Search | `pinterest.com/search/pins/?q=<query>` | `Pinterest/search_<query>/` |
| Pin | `pinterest.com/pin/<id>/` | `Pinterest/pin_<id>/` |

Each file is named by its image content hash (`<hash>.jpg`), so the name is the
same every run — re-click to **resume** a partial download and it only fetches
what's missing, never creating duplicates. That's it.

---

## For the end user (non-technical)

### Install (one-time, ~2 minutes)

1. **Get the extension folder.** You should have a folder called
   `chrome_plugin-pinterest.com` containing `manifest.json` and a few other
   files. Save it somewhere you won't accidentally delete it (e.g.
   `Documents/`).

2. **Open Chrome's extensions page.** Type `chrome://extensions` into the
   address bar and press Enter. (Works the same in Edge, Brave, and other
   Chromium browsers.)

3. **Turn on Developer mode.** Top-right of that page, flip the
   "Developer mode" toggle on.

4. **Click "Load unpacked"** (button appears top-left) and select the
   `chrome_plugin-pinterest.com` folder (the one with `manifest.json` inside).
   The extension appears in the list.

5. **Pin the icon to the toolbar.** Click the puzzle-piece icon (🧩) next to
   the address bar, find "Pinterest board downloader", and click the pin icon.
   The red download icon now sits next to the address bar.

6. **Turn off "ask where to save each file."** Open
   `chrome://settings/downloads` and make sure **"Ask where to save each file
   before downloading"** is **OFF**. Otherwise every single image pops a
   "Save As" dialog — Chrome doesn't let extensions bypass that preference.

### Use it

1. Open a Pinterest **board**, **search results**, or **pin** page (see the
   table above). The toolbar icon is in color on Pinterest pages.
2. Click the icon. The badge shows progress (e.g. `42/137`).
3. When done you'll see a notification and a ✓ on the icon.
4. Find your images in the matching `Downloads/Pinterest/…` subfolder.

For **private** boards, make sure you're logged into Pinterest in the same
browser — the extension reuses your session, so it can only see boards your
account can see. Search results are capped at ~1000 images (search is
effectively endless); the notification says so if the cap is hit.

### Re-running / resuming

Click the icon again on the same page. Because each image's filename is fixed
(its content hash), the extension can tell what it already has: for every image
it checks Chrome's download history for a completed download to that exact path
that's still on disk, and skips it. Only missing or interrupted images are
fetched. So a re-click resumes an interrupted run, and picks up pins added
since last time — without duplicates or renaming.

The one thing it can't see is files you have on disk that *aren't* in Chrome's
download history (e.g. you cleared history, or copied the folder from another
machine). In that case it re-downloads them, but writes to the same hash
filename (`conflictAction: "overwrite"`), so you still won't get duplicates.

Upgrading from an older build that used `0001_…` index prefixes? Those won't be
recognized by the new hash names — delete the board folder once before
rerunning to avoid keeping both copies.

---

## Troubleshooting

**Can I save somewhere other than the Downloads folder?**
Not directly — Chrome only lets extensions write inside the browser's Downloads
directory, so files always land in `Downloads/Pinterest/<board>/`. To collect
them elsewhere, either change Chrome's download location first
(`chrome://settings/downloads` → Location) or move the `Pinterest/` folder
afterward. Filenames are stable (content-hash), so moving/syncing the folder is
safe.

**"Not a downloadable page" notification.**
The icon works on board, search-results, and pin URLs (see the table at the
top), not on the home feed or a bare profile (`pinterest.com/<user>/`). Open
one of the supported pages.

**Icon is greyed out.**
It only activates on Pinterest pages — `pinterest.com` and its country
subdomains (`se.pinterest.com`, …), plus the common country ccTLDs
(`pinterest.co.uk`, `pinterest.com.au`, `pinterest.se`, …). If your country's
domain isn't listed in `host_permissions` in `manifest.json`, add it there
(the icon matcher in `background.js` already accepts any `pinterest.<tld>`).

**Nothing happens / it finds 0 pins.**
Open `chrome://extensions`, find this extension, click "Service worker" /
"Inspect views: service worker" to see logs. A private board while logged out
will come back empty. If the resource API starts returning `403 Invalid
Resource Request`, Pinterest has changed the required request header — see
"Updating" below. When the API path fails, the extension automatically falls
back to scrolling the page — slower, and you'll see a "Scanning board"
notification.

**Images are smaller than the original.**
The extension downloads `i.pinimg.com/originals/…` whenever Pinterest exposes
it. For the rare pin where it doesn't, it probes the `/originals/` URL across
file extensions and falls back to the largest preview (max 736 px wide) only
if none exists. If you're getting previews everywhere, Pinterest may have
changed its API — see "Updating" below.

**Some pins are missing.**
First, the count: a board's pin total counts duplicate repins (the same image
saved more than once) and a few imageless idea/story pins, so the number of
files is normally lower than the board's reported count — that gap is expected,
not loss. Video pins and idea/story pins without a single still image are
skipped (the log notes them); pins inside board sections *are* included
(flattened into the one board folder). A few of the owner's own public pins can
be absent from Pinterest's *signed-in* feed — the extension works around this
by also crawling the board anonymously and merging (see "How it works"). If a
real image is still missing, it's usually a transient CDN hiccup mid-run — each
download is retried 3×, and **re-clicking the icon resumes and grabs anything
left**.

---

## For developers

### Layout

```
manifest.json          MV3 manifest
background.js          Service worker: orchestrates the API crawl + downloads
pinterest.js           Pure helpers (URL parsing, API options, JSON parsing)
content-scroll.js      Self-contained DOM-scroll harvester (fallback only)
icons/                 16/48/128 px PNG icons
test/                  Node --test unit tests + fixtures
package.json           Just for `npm test` — no runtime deps
```

### Run the tests

```bash
npm test        # or: node --test
```

### How the download works

Images come from Pinterest's private **resource API** (the same JSON endpoints
the website itself calls), which yields true originals with the correct file
extension and full pagination — no scrolling required:

1. **Click handler** (`background.js`) calls `parsePinterestUrl(tab.url)`,
   which returns a target descriptor with `kind: "board" | "search" | "pin"`
   (or null for unsupported pages). `collectViaApi` dispatches on `kind`;
   each collector returns `{ folder, entries, capped }`.
2. **Board** (`collectBoard`): `BoardResource` → the board's `id` and name,
   then `BoardFeedResource` paged via `bookmark` cursors until the `-end-`
   sentinel. `filter_section_pins: false` makes the feed span the whole board
   (sections included) — no separate, drift-prone per-section crawl. The feed
   is crawled **twice and unioned**: authenticated (the only view that sees a
   *private* board) and anonymous (the full *public* feed — Pinterest's
   signed-in view sometimes omits a few of the owner's own public pins). For a
   private board the anonymous pass returns nothing and the authenticated set
   stands; the union only ever adds coverage.
   - **Search** (`collectSearch`): `BaseSearchResource` (scope `pins`), paged
     like the feed but bounded by `SEARCH_MAX_PAGES` (search is endless); pins
     are nested under `data.results`. The summary notes if the cap was hit.
   - **Pin** (`collectPin`): `PinResource` → that one pin. (No DOM fallback —
     scrolling a pin page would grab unrelated "more ideas".)
4. For each pin, **`pickPinImage`** takes `images.orig` if present, else the
   largest preview size (the `NNNx` keys; square crops like `136x136` are
   ignored). Previews are upgraded to `/originals/` by probing candidate
   extensions (`upgradeToOriginal`).
5. **De-dupe by content hash** — the `<hash>` in the `i.pinimg.com` path is
   the same image across all sizes, so repins that point at the same file are
   downloaded once.
6. **Filename:** `Pinterest/<folder>/<hash>.<ext>` — deterministic, derived
   from the image's content hash, so the destination for any image is fixed.
   `<folder>` is the board name, `search_<query>`, or `pin_<id>` (`folderName`).
7. **Skip if already present:** `chrome.downloads.search` for a completed
   download to that exact path that still exists on disk (`alreadyHave`).
   Downloads use `conflictAction: "overwrite"` so a forced re-download never
   produces `<hash> (1).<ext>` duplicates.

Every resource call carries two things or Pinterest refuses it: the user's
session (`credentials: "include"`, required for private boards) and an
`x-pinterest-pws-handler` header — without the latter Pinterest returns
`403 Invalid Resource Request`. Downloads are capped at 5 in parallel.

> A board's reported pin count can exceed the number of files you get: idea/
> story pins have no single still image (skipped), some counted pins are
> repins of an image already saved (de-duped), and the counter itself is
> approximate. You get every distinct image the board's own feed returns.

**Fallback:** if the API path returns zero pins (Pinterest changed the API,
logged-out private board, etc.), the worker injects `harvestPinsByScrolling`
(`content-scroll.js`) to auto-scroll the virtualized grid and harvest every
rendered `i.pinimg.com` image, then upgrades those to `/originals/`. It's
slower and capped by what actually renders, but it keeps the extension
working without an API.

### Why the API instead of scraping the DOM?

Pinterest's board grid is virtualized — off-screen pins are removed from the
DOM, so a one-shot DOM read misses most of the board, and DOM thumbnails are
capped at 736 px. The resource API returns the *full original* URL (correct
extension and dimensions) for *every* pin including sections, in a stable
JSON shape. The DOM path is kept only as a resilience fallback. (This is the
opposite trade-off from the sibling chch.ru extension, whose gallery is
fully server-rendered into the DOM — there, reading the DOM is the simplest
correct path.)

### Updating

If Pinterest changes its API, the request/response knowledge is isolated in
`pinterest.js` (option builders, `*FromResponse` parsers, `nextBookmark`,
`pickPinImage`). Update those and run `npm test`. The fixtures under
`test/fixtures/` capture the expected JSON shapes — refresh them from a real
response (DevTools → Network → a `…Resource/get/` call) if the schema drifts.

The one piece that may rot is the **`PWS_HANDLER`** constant in
`background.js`. Pinterest gates resource calls behind the
`x-pinterest-pws-handler` request header (a route-handler name). It's a stable
route identifier rather than a build hash, but if calls start coming back
`403 Invalid Resource Request`, grab the current value from DevTools → Network
→ any `…Resource/get/` request → Request Headers → `x-pinterest-pws-handler`,
and update the constant. (The `x-app-version` build hash, by contrast, isn't
validated — the extension doesn't send it.)
```
