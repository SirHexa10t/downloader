import {
  parsePinterestUrl,
  buildResourceUrl,
  boardResourceOptions,
  boardFeedOptions,
  searchOptions,
  pinOptions,
  relatedPinsOptions,
  boardFromResponse,
  pinsFromResponse,
  searchPinsFromResponse,
  relatedPinsFromResponse,
  pinFromResponse,
  nextBookmark,
  pickPinImage,
  toOriginalsCandidates,
  imageHashFromUrl,
  originalFilenameFromUrl,
  folderName,
  progressPercent,
  crawlBadgeText,
} from "./pinterest.js";
import { harvestPinsByScrolling } from "./content-scroll.js";

const CONCURRENCY = 5; // parallel downloads
const MAX_PAGES = 600; // board pagination safety cap (~15k pins) — prevents a loop
const SEARCH_MAX_PAGES = 800; // search is effectively endless — bound it (~20000 results)
// A pin's related feed normally self-terminates (its bookmark runs out — ~300
// pins for a typical pin), so the crawl gets the WHOLE feed in one run. This is
// only a backstop for the rare feed that keeps paginating, matching search's
// ~20000 ceiling. It is deliberately NOT small: a small cap stops mid-feed, and
// re-clicking can't resume past it (the crawl always restarts at page 0), so
// the tail would be unreachable.
const RELATED_MAX_PAGES = 800;
const DOWNLOAD_ATTEMPTS = 3; // retries per image for transient CDN/network blips
const NOTIFY_EVERY = 250; // emit a progress notification every N images handled
const PIN_RED = "#e60023";
const PROGRESS_ID = "pinterest-downloader-progress"; // reused so pings replace, not stack

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Pinterest rejects every resource-API call that lacks this header with
// "Invalid Resource Request" (HTTP 403) — it's the one required gate (cookies
// aside). The value is the board page's route-handler name: a *stable* route
// identifier, not the per-deploy build hash (which Pinterest doesn't even
// validate — a bogus x-app-version still works). If calls ever start 403ing,
// refresh this from DevTools → Network → any `…Resource/get/` request →
// Request Headers → `x-pinterest-pws-handler`.
const PWS_HANDLER = "www/[username]/[slug].js";

// Toolbar icon is disabled by default; declarativeContent re-enables it on
// any pinterest.com page. Board-vs-not is validated on click (cheaper and more
// robust than a URL regex that has to exclude /pin/, profiles, search, …).
chrome.runtime.onInstalled.addListener(() => {
  chrome.action.disable();
  chrome.declarativeContent.onPageChanged.removeRules(undefined, () => {
    chrome.declarativeContent.onPageChanged.addRules([
      {
        conditions: [
          new chrome.declarativeContent.PageStateMatcher({
            // Any pinterest.<tld> host (pinterest.com, se.pinterest.com,
            // pinterest.co.uk, …) — but not look-alikes like notpinterest.com.
            pageUrl: {
              urlMatches:
                "^https?://([a-z0-9-]+\\.)*pinterest\\.[a-z]{2,3}(\\.[a-z]{2})?/",
            },
          }),
        ],
        actions: [new chrome.declarativeContent.ShowAction()],
      },
    ]);
  });
});

let running = false;

chrome.action.onClicked.addListener(async (tab) => {
  if (running) {
    notify("Already downloading", "A download is already in progress.");
    return;
  }
  running = true;
  try {
    await runDownload(tab);
  } catch (err) {
    console.error("[pinterest-downloader] fatal:", err);
    notify("Download failed", String(err?.message ?? err));
    setBadge("!", "#d1242f");
  } finally {
    running = false;
    setTimeout(() => chrome.action.setBadgeText({ text: "" }), 5000);
  }
});

async function runDownload(tab) {
  const target = parsePinterestUrl(tab.url);
  if (!target) {
    notify(
      "Not a downloadable page",
      "Open a Pinterest board, a search results page, or a pin.",
    );
    return;
  }

  setBadge("…", PIN_RED);

  // Stream images straight to downloads as the API is crawled: each page is
  // saved as soon as it arrives, so downloads start on the first page and the
  // progress already made survives an interrupted run (no "crawl everything,
  // then download" wait). Files are named by content hash, so re-running only
  // fetches what's missing. Board/search fall back to a DOM scroll if the API
  // yields nothing; a pin page doesn't (its API calls — the pin plus its
  // related feed — already cover it).
  const run = newRun(folderName(target));
  let capped = false;
  try {
    capped = await collectAndDownload(run, target);
  } catch (err) {
    console.warn("[pinterest-downloader] API path failed:", err);
  }

  if (run.total === 0 && target.kind !== "pin") {
    console.warn("[pinterest-downloader] API yielded nothing; scrolling DOM.");
    notify("Scanning page", "Reading pins by scrolling the page…");
    const scrolled = await collectViaScroll(tab);
    await downloadEntries(run, scrolled, scrolled.length);
  }

  if (run.total === 0) {
    notify("No images found", "Couldn't find any images on this page.");
    setBadge("0", "#d1242f");
    return;
  }

  const summary =
    `Downloaded ${run.done}, skipped ${run.skipped}` +
    (run.failed > 0 ? `, failed ${run.failed}` : "") +
    ` of ${run.total}` +
    (capped
      ? ` (stopped at the ~${SEARCH_MAX_PAGES * 25}-image safety limit; results beyond it were skipped)`
      : "") +
    ".";
  setBadge(run.failed > 0 ? "!" : "✓", run.failed > 0 ? "#d1242f" : "#1a7f37");
  notify(`Saved to Downloads/${run.folder}`, summary, PROGRESS_ID);
}

// --------------------------------------------------------------------------
// Primary path: Pinterest's private "resource" JSON API. Each collector
// downloads into `run` as it crawls and returns whether it hit the page cap.
// --------------------------------------------------------------------------
function collectAndDownload(run, target) {
  if (target.kind === "search") return collectSearch(run, target);
  if (target.kind === "pin") return collectPin(run, target);
  return collectBoard(run, target);
}

async function collectBoard(run, board) {
  const { origin, username, slug, boardPath } = board;

  // 1. Resolve the board id + display name (authenticated — required to see a
  // private board at all). The name fixes the destination folder.
  const boardObj = boardFromResponse(
    await fetchResource(
      buildResourceUrl(
        origin,
        "BoardResource",
        boardResourceOptions(username, slug),
        boardPath,
      ),
    ),
  );
  const boardId = boardObj?.id;
  if (!boardId) throw new Error("BoardResource returned no board id");
  run.folder = folderName(board, boardObj?.name ?? slug);

  // 2. Crawl the whole feed TWICE and union the results:
  //   - authenticated (credentials:include): the only view that can see a
  //     PRIVATE board's pins, and
  //   - anonymous (credentials:omit): the full PUBLIC feed.
  // Pinterest's signed-in view can omit a few of the owner's own public pins
  // (observed here: 4 of 377 — not dead links, just signed-in-view filtering),
  // while the logged-out view returns them all; the anonymous pass recovers
  // those. For a private board the anonymous pass just returns nothing and the
  // authenticated set stands. The union must be computed before downloading
  // (we de-dupe across both passes), so a board crawls fully, THEN downloads —
  // and because that gives a known total up front, the badge shows a percentage.
  // boardFeedOptions sets filter_section_pins:false, so each pass spans the
  // whole board (sections included) without a separate, drift-prone crawl.
  const feedPass = (authenticated) => {
    const out = [];
    return pageThrough(
      (bm) =>
        fetchResource(
          buildResourceUrl(
            origin,
            "BoardFeedResource",
            boardFeedOptions(boardId, boardPath, bm),
            boardPath,
          ),
          authenticated,
        ),
      // Only the authenticated pass drives the crawl badge — it's the
      // representative full feed, and a single writer keeps the count clean
      // (the two passes run concurrently and would otherwise fight over it).
      (pins, found) => {
        for (const pin of pins) out.push(pin);
        if (authenticated) reportCrawlProgress(found);
      },
    ).then(() => out);
  };
  const [authed, anon] = await Promise.all([feedPass(true), feedPass(false)]);

  const entries = pinsToEntries([...authed, ...anon], run.seen);
  await downloadEntries(run, entries, entries.length);
  return false; // the board feed self-terminates; MAX_PAGES is just a loop guard
}

// Search results (BaseSearchResource), streamed: each page is downloaded as it
// arrives. Single authenticated pass (matches what the user sees), bounded by
// SEARCH_MAX_PAGES since search is effectively endless. Pins are nested under
// data.results, not data. The total isn't known until the feed ends, so the
// badge shows a running count rather than a percentage.
async function collectSearch(run, target) {
  const { origin, query, sourceUrl } = target;
  return pageThrough(
    (bm) =>
      fetchResource(
        buildResourceUrl(origin, "BaseSearchResource", searchOptions(query, bm), sourceUrl),
        true,
      ),
    (pins) => downloadEntries(run, pinsToEntries(pins, run.seen), null),
    { pinsFrom: searchPinsFromResponse, maxPages: SEARCH_MAX_PAGES },
  );
}

// A pin page, streamed: the pin itself (PinResource) downloaded first, then its
// "More like this" related feed (RelatedModulesResource) — the recommendation
// grid shown below the pin, which is what "all the other images on the page"
// refers to — paged to the end of the feed (RELATED_MAX_PAGES is only a
// backstop). Everything de-dupes by hash through the shared run.seen set.
async function collectPin(run, target) {
  const { origin, pinId, sourceUrl } = target;

  const mainPin = pinFromResponse(
    await fetchResource(
      buildResourceUrl(origin, "PinResource", pinOptions(pinId), sourceUrl),
    ),
  );
  if (mainPin) {
    await downloadEntries(run, pinsToEntries([mainPin], run.seen), null);
  }

  return pageThrough(
    (bm) =>
      fetchResource(
        buildResourceUrl(
          origin,
          "RelatedModulesResource",
          relatedPinsOptions(pinId, bm),
          sourceUrl,
        ),
      ),
    (pins) => downloadEntries(run, pinsToEntries(pins, run.seen), null),
    { pinsFrom: relatedPinsFromResponse, maxPages: RELATED_MAX_PAGES },
  );
}

// Drive a paginated resource endpoint until its bookmark is exhausted, handing
// each page's pins to `onPage(pins, found)` — `found` is the running pin count.
// onPage is awaited, so a collector can download a page before the next is
// fetched (streaming). Returns true if it stopped at the page cap (more results
// remained), false if it ran the feed dry or bailed on errors. A page error
// gets one retry, then pagination stops but KEEPS what was already handled —
// one flaky request shouldn't discard a long crawl. opts.pinsFrom selects the
// response shape (board feed vs search vs related); opts.maxPages overrides the cap.
async function pageThrough(getPage, onPage, opts = {}) {
  const pinsFrom = opts.pinsFrom || pinsFromResponse;
  const maxPages = opts.maxPages || MAX_PAGES;
  let bookmark = null;
  let found = 0;
  for (let page = 0; page < maxPages; page++) {
    let json;
    try {
      json = await getPage(bookmark);
    } catch (err) {
      console.warn("[pinterest-downloader] page fetch failed, retrying:", err);
      try {
        json = await getPage(bookmark);
      } catch (err2) {
        console.warn(
          "[pinterest-downloader] page failed again; stopping pagination:",
          err2,
        );
        return false;
      }
    }
    const pins = pinsFrom(json);
    found += pins.length;
    await onPage(pins, found);
    bookmark = nextBookmark(json);
    if (!bookmark) return false;
  }
  console.warn(`[pinterest-downloader] hit ${maxPages}-page cap; stopping.`);
  return true;
}

// Pick each pin's best image and de-dupe by content hash — repins (and any
// other pins pointing at the same file) are downloaded once. `seen` is the
// hash set to de-dupe against; pass a shared set to de-dupe across pages of a
// streamed feed, or omit it for a one-shot batch.
function pinsToEntries(pins, seen = new Set()) {
  const entries = [];
  for (const pin of pins) {
    const img = pickPinImage(pin);
    if (!img) continue;
    const key = imageHashFromUrl(img.url) ?? img.url;
    if (seen.has(key)) continue;
    seen.add(key);
    entries.push({ imageUrl: img.url, isOriginal: img.isOriginal });
  }
  return entries;
}

// --------------------------------------------------------------------------
// Fallback path: scroll the rendered board and harvest <img> URLs.
// --------------------------------------------------------------------------
async function collectViaScroll(tab) {
  const [{ result } = {}] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: harvestPinsByScrolling,
  });
  const harvested = result ?? [];
  const seen = new Set();
  const entries = [];
  for (const { thumbUrl } of harvested) {
    const key = imageHashFromUrl(thumbUrl) ?? thumbUrl;
    if (seen.has(key)) continue;
    seen.add(key);
    // Harvested URLs are previews; mark non-original so downloadOne upgrades
    // them to /originals/ where possible.
    entries.push({ imageUrl: thumbUrl, isOriginal: false });
  }
  return entries;
}

// --------------------------------------------------------------------------
// Download orchestration: shared state for one run + the batch downloader the
// collectors feed (a whole board at once, or one streamed page at a time).
// --------------------------------------------------------------------------

// Mutable tally + cross-page de-dupe state for a single download run.
function newRun(folder) {
  return { folder, seen: new Set(), total: 0, done: 0, skipped: 0, failed: 0, announced: 0 };
}

// Download a batch of already-de-duped entries into `run`, at most CONCURRENCY
// at once, updating the badge and pinging every NOTIFY_EVERY images. Called
// once per board (the full set) or once per streamed page (search/pin).
// `knownTotal` (the final image count, known up front only for a board) drives a
// percentage badge; pass null while streaming a feed whose total isn't known
// yet, and the badge shows a running count instead.
async function downloadEntries(run, entries, knownTotal) {
  run.total += entries.length;
  await runWithConcurrency(entries, CONCURRENCY, async (entry) => {
    try {
      const status = await downloadOne(entry, run.folder);
      if (status === "skipped") run.skipped++;
      else if (status === "ok") run.done++;
      else run.failed++;
    } catch (err) {
      console.warn("[pinterest-downloader] failed", entry.imageUrl, err);
      run.failed++;
    } finally {
      const handled = run.done + run.skipped;
      setBadge(knownTotal ? progressPercent(handled, knownTotal) : crawlBadgeText(handled), PIN_RED);
      // Ping every NOTIFY_EVERY images so a long run shows real progress (the
      // badge alone is easy to miss). Reuses PROGRESS_ID so each ping replaces
      // the last instead of stacking; the final summary (same id) replaces the
      // last ping. Suppressed at a known finish line. No `await` here, so the
      // milestone check is atomic across the concurrent workers.
      if (handled - run.announced >= NOTIFY_EVERY && (!knownTotal || handled < knownTotal)) {
        run.announced = handled;
        const suffix = knownTotal ? ` of ${knownTotal}` : "";
        notify(
          `Downloading… ${handled}${suffix}`,
          `${run.done} saved, ${run.skipped} already had — continuing.`,
          PROGRESS_ID,
        );
      }
    }
  });
}

// --------------------------------------------------------------------------
// Download a single entry.
// --------------------------------------------------------------------------
async function downloadOne(entry, folder) {
  let url = entry.imageUrl;
  if (!entry.isOriginal) url = await upgradeToOriginal(url);

  // Deterministic destination: the i.pinimg.com content hash (<hash>.<ext>).
  // The same image always maps to the same path, which is what makes resume
  // work — and the hash is identical across every size, so an original (.png)
  // and its preview (.jpg) only differ by extension.
  const filename = `${folder}/${originalFilenameFromUrl(url)}`;

  // Resume: skip if this exact file is already in the folder per Chrome's
  // download history and still on disk. Extensions can't read the folder
  // directly, so history is the only "what do I already have" signal.
  if (await alreadyHave(filename)) return "skipped";

  // Retry transient failures with a short backoff. i.pinimg.com occasionally
  // rate-limits or drops a connection under parallel load; without a retry,
  // one blip permanently drops that image from the run (a later re-run's
  // resume would still catch it, but in-run retries make a single pass
  // reliable — this is what caused a batch of pins to go missing).
  let lastState = "unknown";
  for (let attempt = 1; attempt <= DOWNLOAD_ATTEMPTS; attempt++) {
    try {
      const id = await chrome.downloads.download({
        url,
        filename,
        // overwrite (not uniquify): if the file exists but isn't in history
        // (e.g. history cleared), or a previous attempt left a partial file,
        // replace it rather than creating "<hash> (1).<ext>" duplicates.
        conflictAction: "overwrite",
        saveAs: false,
      });
      lastState = await waitForDownload(id);
      if (lastState === "complete") return "ok";
    } catch (err) {
      lastState = `error: ${err?.message ?? err}`;
    }
    if (attempt < DOWNLOAD_ATTEMPTS) await sleep(attempt * 800); // 0.8s, 1.6s
  }
  throw new Error(`Download failed (${lastState}) after ${DOWNLOAD_ATTEMPTS} attempts: ${url}`);
}

// Upgrade a preview URL to the full-resolution /originals/ file. Pinterest
// stores originals under a different extension than the .jpg preview, so probe
// candidates and use the first that exists; fall back to the preview if none
// respond (never download something worse than what we started with).
async function upgradeToOriginal(thumbUrl) {
  for (const candidate of toOriginalsCandidates(thumbUrl)) {
    try {
      const res = await fetch(candidate, { method: "HEAD" });
      if (res.ok) return candidate;
    } catch {
      // network/CORS hiccup — try the next extension
    }
  }
  return thumbUrl;
}

// --------------------------------------------------------------------------
// Low-level helpers.
// --------------------------------------------------------------------------
// authenticated=true sends the user's Pinterest cookies (needed for private
// boards); false makes an anonymous request (the full public feed — see the
// two-pass union in collectBoard).
async function fetchResource(url, authenticated = true) {
  const res = await fetch(url, {
    credentials: authenticated ? "include" : "omit",
    headers: {
      // The required gate — without it Pinterest 403s "Invalid Resource Request".
      "x-pinterest-pws-handler": PWS_HANDLER,
      // Ask for JSON rather than the HTML app shell.
      "x-requested-with": "XMLHttpRequest",
      accept: "application/json, text/javascript, */*; q=0.01",
    },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} on ${url}`);
  return res.json();
}

// Is this exact file already downloaded into this folder and still on disk?
// Matches the destination path's tail in Chrome's download history, tolerant
// of \ vs / separators (Windows vs. *nix). Each path segment is regex-escaped.
async function alreadyHave(relPath) {
  const pattern =
    relPath
      .split("/")
      .map((seg) => seg.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
      .join("[\\\\/]") + "$";
  const matches = await chrome.downloads.search({
    filenameRegex: pattern,
    state: "complete",
    exists: true,
  });
  return matches.length > 0;
}

function waitForDownload(id) {
  return new Promise((resolve) => {
    function listener(delta) {
      if (delta.id !== id || !delta.state) return;
      if (
        delta.state.current === "complete" ||
        delta.state.current === "interrupted"
      ) {
        chrome.downloads.onChanged.removeListener(listener);
        resolve(delta.state.current);
      }
    }
    chrome.downloads.onChanged.addListener(listener);
  });
}

async function runWithConcurrency(items, limit, worker) {
  const queue = [...items];
  const runners = Array.from(
    { length: Math.min(limit, queue.length) },
    async () => {
      while (queue.length > 0) {
        const item = queue.shift();
        await worker(item);
      }
    },
  );
  await Promise.all(runners);
}

function setBadge(text, color) {
  chrome.action.setBadgeText({ text });
  if (color) chrome.action.setBadgeBackgroundColor({ color });
}

// Crawl-phase badge update: show the running count of images discovered while
// paginating, so a long pre-download crawl shows life instead of a frozen "…".
function reportCrawlProgress(found) {
  setBadge(crawlBadgeText(found), PIN_RED);
}

function notify(title, message, id) {
  const options = {
    type: "basic",
    iconUrl: "icons/icon-128.png",
    title,
    message,
  };
  // A fixed id makes the notification replace its predecessor instead of
  // stacking (used for the live progress ping + final summary); omitting it
  // lets Chrome assign a fresh id for one-off messages.
  if (id) chrome.notifications.create(id, options);
  else chrome.notifications.create(options);
}
