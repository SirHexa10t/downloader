import {
  parsePinterestUrl,
  buildResourceUrl,
  boardResourceOptions,
  boardFeedOptions,
  searchOptions,
  pinOptions,
  boardFromResponse,
  pinsFromResponse,
  searchPinsFromResponse,
  pinFromResponse,
  nextBookmark,
  pickPinImage,
  toOriginalsCandidates,
  imageHashFromUrl,
  originalFilenameFromUrl,
  folderName,
} from "./pinterest.js";
import { harvestPinsByScrolling } from "./content-scroll.js";

const CONCURRENCY = 5; // parallel downloads
const MAX_PAGES = 600; // board pagination safety cap (~15k pins) — prevents a loop
const SEARCH_MAX_PAGES = 40; // search is effectively endless — bound it (~800 results)
const DOWNLOAD_ATTEMPTS = 3; // retries per image for transient CDN/network blips
const PIN_RED = "#e60023";

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

  // Collect images. Primary path: the resource API. Fallback (board/search
  // only): scroll the DOM. A single pin doesn't fall back — its API call is
  // reliable, and scrolling a pin page would harvest unrelated "more ideas".
  let folder = folderName(target);
  let entries = [];
  let capped = false;
  try {
    const api = await collectViaApi(target);
    folder = api.folder;
    entries = api.entries;
    capped = api.capped;
  } catch (err) {
    console.warn("[pinterest-downloader] API path failed:", err);
  }

  if (entries.length === 0 && target.kind !== "pin") {
    console.warn("[pinterest-downloader] API yielded nothing; scrolling DOM.");
    notify("Scanning page", "Reading pins by scrolling the page…");
    entries = await collectViaScroll(tab);
  }

  if (entries.length === 0) {
    notify("No images found", "Couldn't find any images on this page.");
    setBadge("0", "#d1242f");
    return;
  }

  // Files are named by the image's content hash (see downloadOne), so the
  // destination for any given image is fixed — re-running only fetches what's
  // missing.
  const total = entries.length;
  let done = 0;
  let skipped = 0;
  let failed = 0;
  setBadge(`0/${total}`, PIN_RED);

  await runWithConcurrency(entries, CONCURRENCY, async (entry) => {
    try {
      const status = await downloadOne(entry, folder);
      if (status === "skipped") skipped++;
      else if (status === "ok") done++;
      else failed++;
    } catch (err) {
      console.warn("[pinterest-downloader] failed", entry.imageUrl, err);
      failed++;
    } finally {
      setBadge(`${done + skipped}/${total}`, PIN_RED);
    }
  });

  const summary =
    `Downloaded ${done}, skipped ${skipped}` +
    (failed > 0 ? `, failed ${failed}` : "") +
    ` of ${total}` +
    (capped ? ` (stopped at the ~${SEARCH_MAX_PAGES * 25}-image search limit)` : "") +
    ".";
  setBadge(failed > 0 ? "!" : "✓", failed > 0 ? "#d1242f" : "#1a7f37");
  notify(`Saved to Downloads/${folder}`, summary);
}

// --------------------------------------------------------------------------
// Primary path: Pinterest's private "resource" JSON API. Each collector
// returns { folder, entries, capped }.
// --------------------------------------------------------------------------
function collectViaApi(target) {
  if (target.kind === "search") return collectSearch(target);
  if (target.kind === "pin") return collectPin(target);
  return collectBoard(target);
}

async function collectBoard(board) {
  const { origin, username, slug, boardPath } = board;

  // 1. Resolve the board id + display name (authenticated — required to see a
  // private board at all).
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
  const boardName = boardObj?.name ?? slug;

  // 2. Crawl the whole feed TWICE and union the results:
  //   - authenticated (credentials:include): the only view that can see a
  //     PRIVATE board's pins, and
  //   - anonymous (credentials:omit): the full PUBLIC feed.
  // Pinterest's signed-in view can omit a few of the owner's own public pins
  // (observed here: 4 of 377 — not dead links, just signed-in-view filtering),
  // while the logged-out view returns them all; the anonymous pass recovers
  // those. For a private board the anonymous pass just returns nothing and the
  // authenticated set stands. Union (concat → de-dupe by hash) can only add
  // coverage, so it's safe either way. boardFeedOptions sets
  // filter_section_pins:false, so each pass spans the whole board (sections
  // included) without a separate, drift-prone per-section crawl.
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
      (pin) => out.push(pin),
    ).then(() => out);
  };
  const [authed, anon] = await Promise.all([feedPass(true), feedPass(false)]);

  return {
    folder: folderName(board, boardName),
    entries: pinsToEntries([...authed, ...anon]),
    capped: false,
  };
}

// Search results (BaseSearchResource). Single authenticated pass — these match
// what the user sees on the page — bounded by SEARCH_MAX_PAGES since search is
// effectively endless. Pins are nested under data.results, not data.
async function collectSearch(target) {
  const { origin, query, sourceUrl } = target;
  const pins = [];
  const capped = await pageThrough(
    (bm) =>
      fetchResource(
        buildResourceUrl(origin, "BaseSearchResource", searchOptions(query, bm), sourceUrl),
        true,
      ),
    (pin) => pins.push(pin),
    { pinsFrom: searchPinsFromResponse, maxPages: SEARCH_MAX_PAGES },
  );
  return { folder: folderName(target), entries: pinsToEntries(pins), capped };
}

// A single pin (PinResource) — just that one image.
async function collectPin(target) {
  const { origin, pinId, sourceUrl } = target;
  const pin = pinFromResponse(
    await fetchResource(
      buildResourceUrl(origin, "PinResource", pinOptions(pinId), sourceUrl),
    ),
  );
  return {
    folder: folderName(target),
    entries: pin ? pinsToEntries([pin]) : [],
    capped: false,
  };
}

// Drive a paginated resource endpoint until its bookmark is exhausted, handing
// every pin to `sink`. Returns true if it stopped at the page cap (more results
// remained), false if it ran the feed dry or bailed on errors. A page error
// gets one retry, then pagination stops but KEEPS what was already collected —
// one flaky request shouldn't discard a long crawl. opts.pinsFrom selects the
// response shape (board feed vs search results); opts.maxPages overrides the cap.
async function pageThrough(getPage, sink, opts = {}) {
  const pinsFrom = opts.pinsFrom || pinsFromResponse;
  const maxPages = opts.maxPages || MAX_PAGES;
  let bookmark = null;
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
    for (const pin of pinsFrom(json)) sink(pin);
    bookmark = nextBookmark(json);
    if (!bookmark) return false;
  }
  console.warn(`[pinterest-downloader] hit ${maxPages}-page cap; stopping.`);
  return true;
}

// Pick each pin's best image and de-dupe by content hash — repins (and any
// other pins pointing at the same file) are downloaded once.
function pinsToEntries(pins) {
  const seen = new Set();
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
// two-pass union in collectViaApi).
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

function notify(title, message) {
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icons/icon-128.png",
    title,
    message,
  });
}
