// Pure helpers for the Pinterest board downloader.
// Dependency-free so they can be unit-tested under `node --test` — all the
// knowledge of Pinterest's URL scheme and private "resource" API JSON shapes
// lives here, so if Pinterest changes something this is usually the only file
// that needs editing (mirrors urls.js in the sibling chch.ru extension).

// First path segment values that are app routes, NOT usernames. A board lives
// at /{username}/{slug}/, which collides structurally with these reserved
// routes, so we exclude them. (Not exhaustive — Pinterest adds routes — but
// covers the ones that actually look like /a/b/.)
const RESERVED_FIRST_SEGMENT = new Set([
  "pin", "search", "ideas", "today", "news_hub", "settings", "business",
  "login", "signup", "about", "help", "discover", "categories", "topics",
  "videos", "cart", "gift", "follow", "unauth", "resource", "v3", "oauth",
  "homefeed", "email", "your_account_settings",
]);

// Parse any downloadable Pinterest page URL into a target descriptor, or null.
// Three kinds are recognized; the `kind` field tells the caller how to crawl:
//
//   board:  /<user>/<slug>/        -> { kind, origin, username, slug, boardPath, sectionSlug }
//   search: /search/pins/?q=...    -> { kind, origin, query, sourceUrl }
//   pin:    /pin/<id>/             -> { kind, origin, pinId, sourceUrl }
//
// Returns null for profiles, the home feed, unsupported search scopes, and
// non-Pinterest hosts.
export function parsePinterestUrl(rawUrl) {
  let u;
  try {
    u = new URL(rawUrl);
  } catch {
    return null;
  }
  // Any Pinterest host: pinterest.com, country subdomains (se.pinterest.com),
  // and country ccTLDs (pinterest.co.uk, pinterest.com.au, pinterest.se). The
  // (^|\.) guard and trailing $ reject look-alikes like notpinterest.com and
  // pinterest.com.evil.com. The manifest's host_permissions are the actual
  // security boundary — this just decides whether to attempt a download.
  if (!/(^|\.)pinterest\.[a-z]{2,3}(\.[a-z]{2})?$/i.test(u.hostname)) return null;

  const segs = u.pathname.split("/").filter(Boolean);

  // A single pin: /pin/<numericId>/
  if (segs[0] === "pin") {
    const pinId = segs[1];
    return /^\d+$/.test(pinId || "")
      ? { kind: "pin", origin: u.origin, pinId, sourceUrl: `/pin/${pinId}/` }
      : null;
  }

  // A pin search: /search/pins/?q=... (we only fetch pin images, not the
  // boards/users search scopes).
  if (segs[0] === "search") {
    if (segs[1] && segs[1] !== "pins") return null;
    const query = (u.searchParams.get("q") || "").trim();
    if (!query) return null;
    return {
      kind: "search",
      origin: u.origin,
      query,
      sourceUrl: `/search/pins/?q=${encodeURIComponent(query)}`,
    };
  }

  // A board: /<username>/<slug>/. A 3rd segment is a board section; we resolve
  // it to the parent board (the whole board is downloaded) but expose
  // sectionSlug. Reserved first segments and _saved/_created tabs aren't boards.
  if (segs.length >= 2) {
    const [username, slug, section] = segs;
    if (RESERVED_FIRST_SEGMENT.has(username.toLowerCase())) return null;
    if (slug.startsWith("_")) return null;
    return {
      kind: "board",
      origin: u.origin,
      username: decodeURIComponent(username),
      slug: decodeURIComponent(slug),
      // Path kept in its on-the-wire (encoded) form for the source_url param.
      boardPath: `/${username}/${slug}/`,
      sectionSlug: section ? decodeURIComponent(section) : null,
    };
  }
  return null;
}

// Pinterest resource endpoints take a `data` query param that is
// URL-encoded JSON of the shape {options, context}. JSON.stringify is enough;
// the caller (buildResourceUrl / URLSearchParams) handles percent-encoding.
export function buildDataParam(options) {
  return JSON.stringify({ options, context: {} });
}

// Build a full GET URL for a Pinterest private resource endpoint, e.g.
//   {origin}/resource/BoardFeedResource/get/?source_url=...&data=...
export function buildResourceUrl(origin, resourceName, options, sourceUrl) {
  const qs = new URLSearchParams();
  if (sourceUrl) qs.set("source_url", sourceUrl);
  qs.set("data", buildDataParam(options));
  return `${origin}/resource/${resourceName}/get/?${qs.toString()}`;
}

// ---- Option builders for each resource (the request side of the API) -------

export function boardResourceOptions(username, slug) {
  return { username, slug, field_set_key: "detailed" };
}

export function boardFeedOptions(boardId, boardPath, bookmark) {
  const options = {
    board_id: boardId,
    board_url: boardPath,
    page_size: 25,
    currentFilter: -1,
    field_set_key: "react_grid_pin",
    // false = include pins that live inside sections, so this one feed returns
    // the entire board (sectioned or not) without a separate section crawl.
    filter_section_pins: false,
    sort: "default",
    layout: "default",
    redux_normalize_feed: true,
  };
  if (bookmark) options.bookmarks = [bookmark];
  return options;
}

// Pin search (BaseSearchResource), scope=pins, paginated via bookmark.
export function searchOptions(query, bookmark) {
  const options = { query, scope: "pins", rs: "typed", redux_normalize_feed: true };
  if (bookmark) options.bookmarks = [bookmark];
  return options;
}

// A single pin (PinResource).
export function pinOptions(pinId) {
  return { id: pinId, field_set_key: "detailed" };
}

// ---- Response parsing (the JSON shapes Pinterest sends back) ---------------

// The board object (id, name, section_count, pin_count) from BoardResource.
export function boardFromResponse(json) {
  const data = json?.resource_response?.data;
  return data && typeof data === "object" && !Array.isArray(data) ? data : null;
}

// The pin array from a board-feed response. Always returns an array.
export function pinsFromResponse(json) {
  const data = json?.resource_response?.data;
  return Array.isArray(data) ? data : [];
}

// Search responses nest the pins under data.results (not data directly).
export function searchPinsFromResponse(json) {
  const results = json?.resource_response?.data?.results;
  return Array.isArray(results) ? results : [];
}

// PinResource returns the single pin object under data.
export function pinFromResponse(json) {
  const d = json?.resource_response?.data;
  return d && typeof d === "object" && !Array.isArray(d) ? d : null;
}

// The pagination cursor for the NEXT page, or null when exhausted. Pinterest
// signals the end with the literal sentinel "-end-". The cursor lives in
// different spots across resources/versions, so check the known locations.
export function nextBookmark(json) {
  const b =
    json?.resource_response?.bookmark ??
    json?.resource?.options?.bookmarks?.[0] ??
    json?.resource_response?.options?.bookmarks?.[0] ??
    null;
  if (!b || b === "-end-") return null;
  return b;
}

// Choose the best image URL for a pin. Prefers the true original
// (images.orig), else the largest preview size key (e.g. "736x"). Returns
// { url, width, height, isOriginal } or null (videos / story pins with no
// still image, deleted pins, etc.).
export function pickPinImage(pin) {
  const imgs = pin?.images;
  if (!imgs || typeof imgs !== "object") return null;

  if (imgs.orig?.url) {
    return {
      url: imgs.orig.url,
      width: imgs.orig.width ?? null,
      height: imgs.orig.height ?? null,
      isOriginal: true,
    };
  }

  let best = null;
  for (const [key, val] of Object.entries(imgs)) {
    const m = /^(\d+)x$/.exec(key); // size keys look like "236x", "736x"
    if (!m || !val?.url) continue;
    const width = parseInt(m[1], 10);
    if (!best || width > best.width) {
      best = { url: val.url, width, height: val.height ?? null, isOriginal: false };
    }
  }
  return best;
}

// Given any i.pinimg.com thumbnail URL, produce candidate /originals/ URLs to
// probe. The hash path is identical across sizes; only the size segment and
// (sometimes) the extension differ. Thumbnails are always served as .jpg even
// when the stored original is a .png/.gif/.webp, so we try the URL's own
// extension first, then the rest. Returns [] if the URL isn't a pinimg image.
export function toOriginalsCandidates(thumbUrl) {
  const m =
    /^https?:\/\/i\.pinimg\.com\/[^/]+\/(.+)\.(jpg|jpeg|png|gif|webp|bmp)$/i.exec(
      thumbUrl,
    );
  if (!m) return [];
  const stem = m[1]; // e.g. "ab/cd/ef/<hash>"
  const own = m[2].toLowerCase();
  const exts = [own, ...["jpg", "png", "gif", "webp"].filter((e) => e !== own)];
  return exts.map((e) => `https://i.pinimg.com/originals/${stem}.${e}`);
}

// The content hash that identifies an image across all its sizes — used to
// de-duplicate pins that appear in both the main feed and a section, and as a
// stable filename stem. Returns null if no hash is present.
export function imageHashFromUrl(url) {
  const m = /\/([0-9a-f]{16,})\.(?:jpg|jpeg|png|gif|webp|bmp)(?:[?#]|$)/i.exec(
    url,
  );
  return m ? m[1].toLowerCase() : null;
}

// The last path segment of a URL, ignoring query/hash. For pinimg originals
// this is "<hash>.<ext>".
export function originalFilenameFromUrl(url) {
  const path = new URL(url).pathname;
  return path.substring(path.lastIndexOf("/") + 1);
}

// "Clara & Eva: vill ha" -> "Clara_Eva_vill_ha". Strips characters disallowed
// on Windows filesystems, collapses whitespace/underscores, caps length.
export function sanitizeName(name) {
  return (
    (name ?? "")
      .replace(/[<>:"/\\|?*\x00-\x1f]/g, "")
      .replace(/\s+/g, "_")
      .replace(/_+/g, "_")
      .replace(/^[._]+|[._]+$/g, "")
      .slice(0, 80) || "board"
  );
}

// Deterministic download subfolder for a target. Same page -> same folder
// every run (so resume works), and distinct across page kinds/inputs:
//   board  -> Pinterest/<board name or slug>
//   search -> Pinterest/search_<query>
//   pin    -> Pinterest/pin_<id>
// `boardName` (the API's display name) is preferred for boards when known.
export function folderName(target, boardName) {
  if (!target) return "Pinterest/download";
  if (target.kind === "search") return `Pinterest/search_${sanitizeName(target.query)}`;
  if (target.kind === "pin") return `Pinterest/pin_${target.pinId}`;
  return `Pinterest/${sanitizeName(boardName ?? target.slug)}`;
}
