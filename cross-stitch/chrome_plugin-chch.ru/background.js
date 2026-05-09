import {
  pickFullSizeForPhoto,
  sanitizeFolderName,
  originalFilenameFromUrl,
} from "./urls.js";
import { extractGalleryEntries } from "./content-extract.js";

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
  const html = await fetchPhotoPage(entry.photoPageUrl);
  const fullUrl = pickFullSizeForPhoto(html, entry.photoId);
  if (!fullUrl) throw new Error(`No full-size image found for ${entry.photoId}`);

  if (await alreadyDownloaded(fullUrl)) return "skipped";

  const filename = `${folder}/${originalFilenameFromUrl(fullUrl)}`;
  const id = await chrome.downloads.download({
    url: fullUrl,
    filename,
    conflictAction: "uniquify",
    saveAs: false,
  });

  await waitForDownload(id);
  return "ok";
}

async function fetchPhotoPage(url) {
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status} on ${url}`);
  // Page is windows-1251 but URLs are pure ASCII, so latin1 decode is safe and
  // never throws on invalid bytes.
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
