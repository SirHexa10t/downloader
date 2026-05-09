# chch.ru gallery downloader

A one-click Chrome extension that downloads every full-size photo from a
chch.ru / gallery.ru album.

Open an album page → click the toolbar icon → all photos save to
`Downloads/chch_<album-name>/`. Filenames are prefixed with the photo's
posted date (`YYYY-MM-DD_…jpg`) so the folder sorts chronologically.
That's it.

---

## For the end user (non-technical)

### Install (one-time, ~2 minutes)

1. **Get the extension folder.** You should have a folder called
   `chch-downloader` containing `manifest.json` and a few other files. Save
   it somewhere you won't accidentally delete it (e.g. `Documents/`).

2. **Open Chrome's extensions page.** In Chrome, type
   `chrome://extensions` into the address bar and press Enter.

3. **Turn on Developer mode.** Top-right of that page, flip the
   "Developer mode" toggle on.

4. **Click "Load unpacked".** A button appears top-left. Click it.

5. **Select the `chch-downloader` folder** (the one with `manifest.json`
   inside) and click "Select Folder" / "Open". The extension appears in the
   list.

6. **Pin the icon to the toolbar.** Click the puzzle-piece icon (🧩) next
   to the address bar. Find "chch.ru gallery downloader" in the dropdown and
   click the pin icon next to it. The blue download icon now sits next to the
   address bar.

7. **Turn off "ask where to save each file."** In Chrome, open Settings
   → Downloads (or paste `chrome://settings/downloads` into the address
   bar). Make sure **"Ask where to save each file before downloading"** is
   **OFF**. If it's on, every single one of the 200+ photos will pop up a
   "Save As" dialog — Chrome doesn't let extensions bypass that user
   preference.

### Use it

1. Open any chch.ru album page (e.g.
   `https://chch.ru/watch?a=bI8i-pYLF`). The extension's toolbar icon
   becomes active (in color).
2. Click the icon. Downloads start immediately.
3. The icon shows progress as a small badge (e.g. `12/203`).
4. When done, you'll see a notification and the icon shows ✓.
5. Find your photos in `Downloads/chch_<album-name>/`.

### Re-running

Click the icon again on the same page. For each photo:

- If you already have a copy with the **same date-prefixed filename** and
  it's the same size or larger, it's **skipped**.
- If your copy is smaller (you're upgrading from an older version that
  grabbed the `m750x740` preview), the original is downloaded and the older
  smaller file is **deleted** so the album folder stays clean.
- If your copy is full-size but doesn't have the date prefix (you're
  upgrading from a version before date-prefixed filenames), it's
  re-downloaded with the new name and the old file is **deleted**. This
  one-time bandwidth cost is the price of rename-without-rename-API.
- If you don't have a copy yet, it's downloaded.

This is also how interrupted downloads recover: rerun and only the missing
photos come down.

---

## Troubleshooting

**Icon stays grey on a chch.ru page.**
The icon only activates on pages that contain a photo gallery (a `mygallery`
element). Make sure you're on the album / "watch" page, not the home page or
a single-photo page.

**Nothing happens when I click.**
Open Chrome's extensions page (`chrome://extensions`), find this extension,
and click "Service worker" / "Inspect views: service worker" to see error
logs.

**"No full-size image found" errors.**
chch.ru's URL scheme may have changed. Check the regex in `urls.js`
(`GALLERY_IMG_RE`) and the photo page format.

**Downloads going somewhere weird.**
Chrome saves to your default Downloads folder. To change it: Chrome menu →
Settings → Downloads → Location.

**Photos that download are tiny (~4 KB) and look like a "very small outfile"
notice.**
chch.ru gates its `-src-` (original) URLs behind login and serves a
placeholder image to anonymous users. The extension avoids `-src-` and
instead drills into the "Оригинал" subpanel (`?subpanel=zoom&zoom=8`),
which exposes a different empty-size URL that returns the actual original.
If you're still getting placeholders, your `urls.js` / `background.js` are
out of date.

**Photos download but they're smaller than the "Оригинал" version I see
when I click manually.**
That was the bug fixed in this version. The extension now follows the
zoom=8 link the same way the website's "Оригинал" button does. If you've
upgraded from an older version, just rerun on the same album — the smaller
files are detected and replaced with the originals automatically.

---

## For developers

### Layout

```
manifest.json          MV3 manifest
background.js          Service worker: orchestrates downloads
content-extract.js     Function injected into the page to read the gallery
urls.js                Pure URL helpers (testable in Node)
icons/                 16/48/128 px PNG icons
test/                  Node --test unit tests + fixtures
package.json           Just for `npm test` — no runtime deps
```

### Run the tests

```bash
node --test
```

### How the download works

1. **Click handler** (`background.js`) injects `extractGalleryEntries` into
   the active tab via `chrome.scripting.executeScript`.
2. The injected function reads `#mygallery`, returns a list of
   `{photoPageUrl, photoId}` pairs and the album name from the `<h1>`.
3. For each entry, the service worker fires two requests **in parallel**:
   - `?subpanel=zoom&zoom=8` page → empty-size original URL
     (`…/<albumId>-<hash>-<photoId>--<hash>.jpg`), the same image the site
     loads when you click "Оригинал". Often >5x bigger than `m750x740`.
   - `?subpanel=main_body` JSON → the sidebar HTML containing the photo's
     posted date in a `day=YYYY-MM-DD` link param.
4. **HEAD request** confirms the new file's size, then
   `chrome.downloads.search` looks for any prior download for this photoId
   in the target folder (regardless of filename — handles cross-version
   upgrades).
5. **Filename:** `<YYYY-MM-DD>_<original-filename>`. Missing date falls
   back to `0000-00-00_…` so the format stays consistent.
6. **Decision:** skip if existing matches both the new filename AND has
   size ≥ new; otherwise download with `conflictAction: "overwrite"`. If
   the existing file lived under a different name (cross-version upgrade
   or undated empty-size from a previous build), it's deleted after the
   new download completes.
7. Falls back to `pickFullSizeForPhoto` (largest `m{W}x{H}`) if zoom=8
   doesn't expose an empty-size URL — defensive for unusual entries like
   videos.

Concurrency is capped at 5 parallel fetches. Each entry triggers three
chch.ru requests (zoom page + main_body + HEAD) plus the download itself.

### Why a regex instead of `DOMParser`?

`DOMParser` isn't available in MV3 service workers without an offscreen
document. The URL pattern is stable, the `photoId` filter eliminates
ambiguity, and the test suite covers the parsing — regex was the simpler
trade.

### Updating

If chch.ru changes its URL scheme, only `urls.js` needs editing. Run
`node --test` to verify.
