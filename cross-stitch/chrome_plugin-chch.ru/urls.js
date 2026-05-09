// Pure helpers for parsing chch.ru / gallery.ru URLs.
// Kept dependency-free so they can be unit-tested under `node --test`.

// A gallery image URL looks like:
//   https://data31.chch.ru/albums/gallery/372752-a651b-105637575-200-ub8995.jpg
// Parts: {host}/{albumId}-{mid-hash}-{photoId}-{size}-{trailing-hash}.jpg
// Trailing hash is typically a `u`-prefixed hex (e.g. `ub8995`).
const GALLERY_IMG_RE =
  /^https?:\/\/data\d+\.chch\.ru\/albums\/gallery\/(\d+)-([a-z0-9]+)-(\d+)-([^-]+)-([a-z0-9]+)\.(jpg|jpeg|png|gif|webp)$/i;

// Image size segment ranking. We *avoid* `src` even though it sounds like the
// original — chch.ru gates that URL and serves a 3.9KB "very small outfile"
// placeholder PNG to anonymous requests. The `m{W}x{H}` variants are the
// largest reliably-public size (matches what the site itself shows). Plain
// pixel widths are fallback. `src`, cropped thumbs (`c80`), and unknown
// segments rank last.
export function sizeRank(sizeSegment) {
  const matrix = sizeSegment.match(/^m(\d+)x(\d+)$/);
  if (matrix) {
    // Bias matrix sizes above pixel-width sizes so a 200x300 preview still
    // beats a 400 thumb.
    return 1_000_000 + parseInt(matrix[1], 10) * parseInt(matrix[2], 10);
  }
  if (/^\d+$/.test(sizeSegment)) return parseInt(sizeSegment, 10);
  return -1;
}

export function parseGalleryUrl(url) {
  const m = url.match(GALLERY_IMG_RE);
  if (!m) return null;
  const [, albumId, midHash, photoId, size, trailingHash, ext] = m;
  return { albumId, midHash, photoId, size, trailingHash, ext, url };
}

// From a photo page's HTML body, find all gallery image URLs that match a
// given photoId, and pick the largest. Returns the chosen URL or null.
export function pickFullSizeForPhoto(photoPageHtml, photoId) {
  const re = new RegExp(
    `https?:\\/\\/data\\d+\\.chch\\.ru\\/albums\\/gallery\\/\\d+-[a-z0-9]+-${photoId}-[^"'\\s<>]+\\.(?:jpg|jpeg|png|gif|webp)`,
    "gi",
  );
  const seen = new Set();
  const candidates = [];
  for (const match of photoPageHtml.matchAll(re)) {
    const url = match[0];
    if (seen.has(url)) continue;
    seen.add(url);
    const parsed = parseGalleryUrl(url);
    if (parsed) candidates.push(parsed);
  }
  if (candidates.length === 0) return null;
  candidates.sort((a, b) => sizeRank(b.size) - sizeRank(a.size));
  return candidates[0].url;
}

// "Eva Rosenstad" -> "Eva_Rosenstad". Strips characters disallowed on Windows
// filesystems and trims runs of whitespace / underscores.
export function sanitizeFolderName(name) {
  return (name ?? "")
    .replace(/[<>:"/\\|?*\x00-\x1f]/g, "")
    .replace(/\s+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^[._]+|[._]+$/g, "")
    .slice(0, 80) || "album";
}

export function originalFilenameFromUrl(url) {
  const path = new URL(url).pathname;
  return path.substring(path.lastIndexOf("/") + 1);
}
