import {
  extractOriginalUrl,
  extractPostedDate,
  pickFullSizeForPhoto,
  sanitizeFolderName,
  originalFilenameFromUrl,
} from "./urls.js";
import { extractGalleryEntries } from "./content-extract.js";

const UNKNOWN_DATE = "0000-00-00";

const CONCURRENCY = 5;

// Toolbar icon is disabled by default. declarativeContent re-enables it only
// on chch.ru pages that actually contain a #mygallery div.
chrome.runtime.onInstalled.addListener(() => {
  chrome.action.disable();
  chrome.declarativeContent.onPageChanged.removeRules(undefined, () => {
    chrome.declarativeContent.onPageChanged.addRules([
      {
        conditions: [
          new chrome.declarativeContent.PageStateMatcher({
            pageUrl: { hostSuffix: "chch.ru" },
            css: ["div#mygallery"],
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
    console.error("[chch-downloader] fatal:", err);
    notify("Download failed", String(err?.message ?? err));
  } finally {
    running = false;
    setTimeout(() => chrome.action.setBadgeText({ text: "" }), 5000);
  }
});

async function runDownload(tab) {
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: extractGalleryEntries,
  });

  if (!result?.ok) {
    notify("No gallery found", "Open a chch.ru album page and try again.");
    return;
  }

  const { albumName, entries } = result;
  if (entries.length === 0) {
    notify("Empty gallery", "Couldn't find any photos on this page.");
    return;
  }

  const folder = `chch_${sanitizeFolderName(albumName)}`;
  setBadge(`0/${entries.length}`, "#1f6feb");

  let done = 0;
  let skipped = 0;
  let failed = 0;

  await runWithConcurrency(entries, CONCURRENCY, async (entry) => {
    try {
      const status = await downloadOne(entry, folder);
      if (status === "skipped") skipped++;
      else if (status === "ok") done++;
      else failed++;
    } catch (err) {
      console.warn("[chch-downloader] failed", entry.photoPageUrl, err);
      failed++;
    } finally {
      setBadge(`${done + skipped}/${entries.length}`, "#1f6feb");
    }
  });

  const summary =
    `Downloaded ${done}, skipped ${skipped}` +
    (failed > 0 ? `, failed ${failed}` : "") +
    ` of ${entries.length}.`;
  setBadge(failed > 0 ? "!" : "✓", failed > 0 ? "#d1242f" : "#1a7f37");
  notify(`Saved to Downloads/${folder}`, summary);
}

async function downloadOne(entry, folder) {
  // Two sibling fetches: the zoom=8 page gives us the empty-size original
  // URL; the main_body subpanel returns JSON whose sidebar contains the
  // photo's "Размещено" (posted) date. They're independent, so do them in
  // parallel.
  const zoomUrl = `${entry.photoPageUrl}&subpanel=zoom&zoom=8`;
  const mainBodyUrl = `${entry.photoPageUrl}&subpanel=main_body`;
  const [zoomHtml, mainBodyText] = await Promise.all([
    fetchPage(zoomUrl),
    fetchPage(mainBodyUrl),
  ]);

  let imageUrl = extractOriginalUrl(zoomHtml, entry.photoId);
  if (!imageUrl) {
    // Fallback: zoom=8 didn't surface an empty-size URL for this photo
    // (e.g. video, deleted, or unusual album). Use the regular photo page.
    const photoHtml = await fetchPage(entry.photoPageUrl);
    imageUrl = pickFullSizeForPhoto(photoHtml, entry.photoId);
  }
  if (!imageUrl) {
    throw new Error(`No image URL found for photoId ${entry.photoId}`);
  }

  if (await alreadyDownloaded(imageUrl)) return "skipped";

  const dateStr = extractPostedDate(mainBodyText) ?? UNKNOWN_DATE;
  const filename = `${folder}/${dateStr}_${originalFilenameFromUrl(imageUrl)}`;
  const id = await chrome.downloads.download({
    url: imageUrl,
    filename,
    conflictAction: "uniquify",
    saveAs: false,
  });
  const finalState = await waitForDownload(id);
  if (finalState !== "complete") {
    throw new Error(`Download ${finalState}: ${imageUrl}`);
  }
  return "ok";
}

async function fetchPage(url) {
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status} on ${url}`);
  // Pages are windows-1251 but URLs are pure ASCII, so latin1 decode is safe
  // and never throws on invalid bytes.
  const buf = await res.arrayBuffer();
  return new TextDecoder("latin1").decode(buf);
}

async function alreadyDownloaded(url) {
  const matches = await chrome.downloads.search({ url, exists: true });
  return matches.length > 0;
}

function waitForDownload(id) {
  return new Promise((resolve) => {
    function listener(delta) {
      if (delta.id !== id || !delta.state) return;
      if (delta.state.current === "complete" ||
          delta.state.current === "interrupted") {
        chrome.downloads.onChanged.removeListener(listener);
        resolve(delta.state.current);
      }
    }
    chrome.downloads.onChanged.addListener(listener);
  });
}

async function runWithConcurrency(items, limit, worker) {
  const queue = [...items];
  const runners = Array.from({ length: Math.min(limit, queue.length) }, async () => {
    while (queue.length > 0) {
      const item = queue.shift();
      await worker(item);
    }
  });
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
