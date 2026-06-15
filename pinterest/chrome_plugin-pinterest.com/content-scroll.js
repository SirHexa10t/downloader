// Fallback harvester, injected into the board tab via
// chrome.scripting.executeScript({func}). Used ONLY when the resource API
// path in background.js returns nothing (Pinterest changed the API, the user
// isn't logged in for a private board, etc.). It auto-scrolls the virtualized
// board grid, collecting every pin image that renders.
//
// Must be fully self-contained — Chrome serializes the function source and
// runs it in the page world, so it can't import from pinterest.js. The small
// helpers here intentionally mirror their pinterest.js counterparts.
export async function harvestPinsByScrolling() {
  const found = new Map(); // image-hash -> { thumbUrl, pinId }
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const hashOf = (url) => {
    const m = /\/([0-9a-f]{16,})\.(?:jpg|jpeg|png|gif|webp|bmp)/i.exec(url);
    return m ? m[1].toLowerCase() : null;
  };

  // Pick the largest pinimg URL an <img> offers: srcset's last (widest)
  // candidate if present, else currentSrc/src.
  const bestFromImg = (img) => {
    const ss = img.getAttribute("srcset");
    if (ss) {
      const cands = ss
        .split(",")
        .map((s) => s.trim().split(/\s+/)[0])
        .filter((u) => u && u.includes("i.pinimg.com"));
      if (cands.length) return cands[cands.length - 1];
    }
    const src = img.currentSrc || img.src || "";
    return src.includes("i.pinimg.com") ? src : null;
  };

  const harvest = () => {
    // Pair each image with its pin id via the enclosing /pin/<id>/ anchor.
    for (const a of document.querySelectorAll('a[href*="/pin/"]')) {
      const img = a.querySelector("img");
      if (!img) continue;
      const url = bestFromImg(img);
      if (!url) continue;
      const hash = hashOf(url);
      if (!hash || found.has(hash)) continue;
      const pm = a.getAttribute("href").match(/\/pin\/([^/]+)/);
      found.set(hash, { thumbUrl: url, pinId: pm ? pm[1] : null });
    }
    // Catch any pinimg images not wrapped in a pin anchor.
    for (const img of document.querySelectorAll(
      'img[src*="i.pinimg.com"], img[srcset*="i.pinimg.com"]',
    )) {
      const url = bestFromImg(img);
      if (!url) continue;
      const hash = hashOf(url);
      if (hash && !found.has(hash)) found.set(hash, { thumbUrl: url, pinId: null });
    }
  };

  // Scroll to the bottom in steps, harvesting as virtualized rows mount.
  // Stop once both the pin count and page height hold steady for several
  // rounds (board fully loaded) or we hit the hard iteration ceiling.
  let stable = 0;
  let lastCount = -1;
  let lastHeight = -1;
  for (let i = 0; i < 1500 && stable < 5; i++) {
    harvest();
    window.scrollBy(0, Math.round(window.innerHeight * 0.9));
    await sleep(450);
    const height = document.documentElement.scrollHeight;
    if (found.size === lastCount && height === lastHeight) stable++;
    else stable = 0;
    lastCount = found.size;
    lastHeight = height;
  }
  harvest();

  return Array.from(found.values());
}
