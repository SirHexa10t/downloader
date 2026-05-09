// Self-contained extractor injected into the active gallery tab via
// `chrome.scripting.executeScript({func: ...})`. Must not import anything —
// Chrome serializes the function source and runs it in the page's world.
export function extractGalleryEntries() {
  const gallery = document.getElementById("mygallery");
  if (!gallery) return { ok: false, reason: "no_gallery" };

  const albumName =
    document.querySelector("h1")?.textContent?.trim() || "album";

  const entries = [];
  for (const a of gallery.querySelectorAll('a[href*="?ph="]')) {
    const img = a.querySelector("img");
    if (!img) continue;
    const m = img.src.match(
      /\/albums\/gallery\/\d+-[a-f0-9]+-(\d+)-/i,
    );
    if (!m) continue;
    entries.push({
      photoPageUrl: new URL(a.getAttribute("href"), location.href).href,
      photoId: m[1],
    });
  }

  // De-dup by photoId (a gallery may render duplicates).
  const seen = new Set();
  const unique = entries.filter((e) => {
    if (seen.has(e.photoId)) return false;
    seen.add(e.photoId);
    return true;
  });

  return { ok: true, albumName, entries: unique };
}
