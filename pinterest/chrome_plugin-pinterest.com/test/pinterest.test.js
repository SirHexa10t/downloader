import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  parsePinterestUrl,
  buildDataParam,
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
  sanitizeName,
  folderName,
  progressPercent,
  crawlBadgeText,
} from "../pinterest.js";

const fixture = (name) =>
  JSON.parse(
    readFileSync(fileURLToPath(new URL(`./fixtures/${name}`, import.meta.url))),
  );

// ------------------------------------------------------------ parsePinterestUrl
test("parsePinterestUrl: board on a country subdomain", () => {
  assert.deepEqual(
    parsePinterestUrl("https://se.pinterest.com/enfald/clara-eva-vill-ha/"),
    {
      kind: "board",
      origin: "https://se.pinterest.com",
      username: "enfald",
      slug: "clara-eva-vill-ha",
      boardPath: "/enfald/clara-eva-vill-ha/",
      sectionSlug: null,
    },
  );
});

test("parsePinterestUrl: board www/apex, trailing slash optional, query ignored", () => {
  assert.equal(
    parsePinterestUrl("https://www.pinterest.com/enfald/clara-eva-vill-ha").slug,
    "clara-eva-vill-ha",
  );
  assert.equal(
    parsePinterestUrl("https://pinterest.com/enfald/clara-eva-vill-ha/?invite=1")
      .username,
    "enfald",
  );
});

test("parsePinterestUrl: a board section resolves to the parent board", () => {
  const b = parsePinterestUrl(
    "https://www.pinterest.com/enfald/clara-eva-vill-ha/klara/",
  );
  assert.equal(b.kind, "board");
  assert.equal(b.boardPath, "/enfald/clara-eva-vill-ha/");
  assert.equal(b.sectionSlug, "klara");
});

test("parsePinterestUrl: search pins page", () => {
  assert.deepEqual(
    parsePinterestUrl(
      "https://www.pinterest.com/search/pins/?q=Eva%20Rosenstand&rs=typed",
    ),
    {
      kind: "search",
      origin: "https://www.pinterest.com",
      query: "Eva Rosenstand",
      sourceUrl: "/search/pins/?q=Eva%20Rosenstand",
    },
  );
});

test("parsePinterestUrl: search needs a query; only the pins scope", () => {
  assert.equal(parsePinterestUrl("https://www.pinterest.com/search/pins/?q="), null);
  assert.equal(parsePinterestUrl("https://www.pinterest.com/search/pins/"), null);
  assert.equal(parsePinterestUrl("https://www.pinterest.com/search/boards/?q=x"), null);
  // bare /search/?q= (no scope segment) defaults to pins
  assert.equal(parsePinterestUrl("https://www.pinterest.com/search/?q=cats").kind, "search");
});

test("parsePinterestUrl: single pin page (utm junk ignored)", () => {
  assert.deepEqual(
    parsePinterestUrl(
      "https://www.pinterest.com/pin/14777505018982287/?utm_campaign=x&e_t=y",
    ),
    {
      kind: "pin",
      origin: "https://www.pinterest.com",
      pinId: "14777505018982287",
      sourceUrl: "/pin/14777505018982287/",
    },
  );
});

test("parsePinterestUrl: non-numeric / missing pin id rejected", () => {
  assert.equal(parsePinterestUrl("https://www.pinterest.com/pin/not-a-number/"), null);
  assert.equal(parsePinterestUrl("https://www.pinterest.com/pin/"), null);
});

test("parsePinterestUrl: rejects profiles, home, and profile tabs", () => {
  assert.equal(parsePinterestUrl("https://www.pinterest.com/enfald/"), null);
  assert.equal(parsePinterestUrl("https://www.pinterest.com/"), null);
  assert.equal(parsePinterestUrl("https://www.pinterest.com/enfald/_saved/"), null);
  assert.equal(parsePinterestUrl("https://www.pinterest.com/enfald/_created/"), null);
});

test("parsePinterestUrl: boards on ccTLDs and country subdomains", () => {
  for (const host of [
    "www.pinterest.co.uk",
    "pinterest.com.au",
    "pinterest.se",
    "pinterest.fr",
    "uk.pinterest.com",
  ]) {
    const b = parsePinterestUrl(`https://${host}/enfald/clara-eva-vill-ha/`);
    assert.equal(b?.kind, "board", `expected board for ${host}`);
    assert.equal(b.origin, `https://${host}`);
  }
});

test("parsePinterestUrl: rejects non-Pinterest hosts (incl. lookalikes)", () => {
  assert.equal(parsePinterestUrl("https://example.com/enfald/board/"), null);
  assert.equal(parsePinterestUrl("https://notpinterest.com/enfald/board/"), null);
  assert.equal(parsePinterestUrl("https://pinterest.com.evil.com/a/b/"), null);
  assert.equal(parsePinterestUrl("not a url"), null);
});

test("folderName: deterministic and distinct per kind", () => {
  assert.equal(
    folderName({ kind: "board", slug: "clara-eva-vill-ha" }, "Clara Eva vill ha"),
    "Pinterest/Clara_Eva_vill_ha",
  );
  assert.equal(
    folderName({ kind: "board", slug: "clara-eva-vill-ha" }),
    "Pinterest/clara-eva-vill-ha", // no API name -> slug
  );
  assert.equal(
    folderName({ kind: "search", query: "Eva Rosenstand" }),
    "Pinterest/search_eva_rosenstand", // query is lower-cased (case-insensitive search)
  );
  assert.equal(
    folderName({ kind: "pin", pinId: "14777505018982287" }),
    "Pinterest/pin_14777505018982287",
  );
});

test("folderName: differently-cased searches share ONE folder (resume works)", () => {
  // The whole point of case-folding the query: "Eva Rosenstand" typed and
  // "eva rosenstand" via autocomplete must not split into two download folders.
  assert.equal(
    folderName({ kind: "search", query: "Eva Rosenstand" }),
    folderName({ kind: "search", query: "eva rosenstand" }),
  );
});

// ------------------------------------------------------- resource URL building
test("buildDataParam wraps options with an empty context", () => {
  assert.deepEqual(JSON.parse(buildDataParam({ board_id: "7" })), {
    options: { board_id: "7" },
    context: {},
  });
});

test("buildResourceUrl: encodes source_url + data and round-trips the JSON", () => {
  const url = buildResourceUrl(
    "https://se.pinterest.com",
    "BoardFeedResource",
    { board_id: "550775982164965310", page_size: 25 },
    "/enfald/clara-eva-vill-ha/",
  );
  assert.ok(
    url.startsWith(
      "https://se.pinterest.com/resource/BoardFeedResource/get/?",
    ),
  );
  const parsed = new URL(url);
  assert.equal(
    parsed.searchParams.get("source_url"),
    "/enfald/clara-eva-vill-ha/",
  );
  assert.deepEqual(JSON.parse(parsed.searchParams.get("data")), {
    options: { board_id: "550775982164965310", page_size: 25 },
    context: {},
  });
});

test("boardFeedOptions: includes bookmarks only when a cursor is given", () => {
  assert.equal(boardFeedOptions("7", "/a/b/", null).bookmarks, undefined);
  assert.deepEqual(
    boardFeedOptions("7", "/a/b/", "CURSOR").bookmarks,
    ["CURSOR"],
  );
});

test("boardFeedOptions: filter_section_pins is false so the feed spans the whole board", () => {
  // The whole sections-vs-loose design hinges on this — section pins must come
  // back in the main feed, since we don't crawl sections separately.
  assert.equal(boardFeedOptions("7", "/a/b/").filter_section_pins, false);
});

test("boardResourceOptions carries the right keys", () => {
  assert.deepEqual(boardResourceOptions("u", "s"), {
    username: "u",
    slug: "s",
    field_set_key: "detailed",
  });
});

test("searchOptions: scope=pins, bookmarks only when given", () => {
  assert.equal(searchOptions("cats").scope, "pins");
  assert.equal(searchOptions("cats").query, "cats");
  assert.equal(searchOptions("cats").bookmarks, undefined);
  assert.deepEqual(searchOptions("cats", "C").bookmarks, ["C"]);
});

test("pinOptions: id + detailed field set", () => {
  assert.deepEqual(pinOptions("123"), { id: "123", field_set_key: "detailed" });
});

test("relatedPinsOptions: pin_id + page_size, bookmarks only when given", () => {
  assert.deepEqual(relatedPinsOptions("123"), { pin_id: "123", page_size: 25 });
  assert.deepEqual(relatedPinsOptions("123", "C").bookmarks, ["C"]);
  assert.equal(relatedPinsOptions("123").bookmarks, undefined);
});

test("relatedPinsOptions: MUST NOT send a field_set_key", () => {
  // Sending one makes Pinterest return imageless pin stubs — the bug this
  // whole resource call works around. Pin this so a future edit can't add it.
  assert.equal("field_set_key" in relatedPinsOptions("123"), false);
  assert.equal("field_set_key" in relatedPinsOptions("123", "C"), false);
});

// ------------------------------------------------------------ response parsing
test("boardFromResponse: pulls the board object from BoardResource", () => {
  const board = boardFromResponse(fixture("board_resource_sample.json"));
  assert.equal(board.id, "550775982164965310");
  assert.equal(board.name, "Clara & Eva vill ha");
});

test("boardFromResponse: null when data is an array or missing", () => {
  assert.equal(boardFromResponse({ resource_response: { data: [] } }), null);
  assert.equal(boardFromResponse({}), null);
});

test("pinsFromResponse: returns the pin array, or [] when absent", () => {
  const pins = pinsFromResponse(fixture("board_feed_sample.json"));
  assert.equal(pins.length, 3);
  assert.deepEqual(pinsFromResponse({}), []);
  assert.deepEqual(pinsFromResponse({ resource_response: { data: {} } }), []);
});

test("searchPinsFromResponse: reads the nested data.results array", () => {
  assert.equal(
    searchPinsFromResponse({ resource_response: { data: { results: [{ id: 1 }, { id: 2 }] } } }).length,
    2,
  );
  assert.deepEqual(searchPinsFromResponse({ resource_response: { data: {} } }), []);
  assert.deepEqual(searchPinsFromResponse({}), []);
});

test("relatedPinsFromResponse: keeps image-bearing pins, drops shelf modules", () => {
  // The fixture mixes 2 real pins with 2 non-pin {type:"story"} shelf modules.
  const pins = relatedPinsFromResponse(fixture("related_modules_sample.json"));
  assert.equal(pins.length, 2);
  assert.deepEqual(
    pins.map((p) => p.id),
    ["9000000000000001", "9000000000000002"],
  );
  // And the kept pins flow through the normal image picker (orig + preview).
  assert.equal(pickPinImage(pins[0]).isOriginal, true);
  assert.equal(pickPinImage(pins[1]).isOriginal, false);
});

test("relatedPinsFromResponse: [] when data is missing or not an array", () => {
  assert.deepEqual(relatedPinsFromResponse({}), []);
  assert.deepEqual(relatedPinsFromResponse({ resource_response: { data: {} } }), []);
});

test("nextBookmark: reads the related-feed cursor too", () => {
  assert.equal(
    nextBookmark(fixture("related_modules_sample.json")),
    "UmVsYXRlZE5leHRQYWdl",
  );
});

test("pinFromResponse: reads the single pin object, null otherwise", () => {
  assert.equal(pinFromResponse({ resource_response: { data: { id: "x" } } }).id, "x");
  assert.equal(pinFromResponse({ resource_response: { data: [] } }), null);
  assert.equal(pinFromResponse({}), null);
});

test("nextBookmark: reads resource_response.bookmark", () => {
  assert.equal(
    nextBookmark(fixture("board_feed_sample.json")),
    "Y2JNCXV0WGc6cGdSaW5nZQ==",
  );
});

test("nextBookmark: reads the resource.options fallback location", () => {
  assert.equal(
    nextBookmark({ resource: { options: { bookmarks: ["NEXT"] } } }),
    "NEXT",
  );
});

test("nextBookmark: null on the -end- sentinel and when absent", () => {
  assert.equal(nextBookmark({ resource_response: { bookmark: "-end-" } }), null);
  assert.equal(nextBookmark({ resource_response: {} }), null);
  assert.equal(nextBookmark({}), null);
});

// --------------------------------------------------------------- pickPinImage
test("pickPinImage: prefers the true original (and reports its ext/dims)", () => {
  const [pin] = pinsFromResponse(fixture("board_feed_sample.json"));
  const img = pickPinImage(pin);
  assert.equal(img.url.endsWith(".png"), true);
  assert.equal(img.url.includes("/originals/"), true);
  assert.equal(img.isOriginal, true);
  assert.equal(img.width, 1500);
});

test("pickPinImage: falls back to the largest preview when no orig", () => {
  const pin = pinsFromResponse(fixture("board_feed_sample.json"))[1];
  const img = pickPinImage(pin);
  assert.match(img.url, /\/736x\//);
  assert.equal(img.isOriginal, false);
  assert.equal(img.width, 736);
});

test("pickPinImage: null for pins with no usable image", () => {
  const pin = pinsFromResponse(fixture("board_feed_sample.json"))[2];
  assert.equal(pickPinImage(pin), null);
  assert.equal(pickPinImage({}), null);
  assert.equal(pickPinImage(null), null);
});

// ------------------------------------------------------- toOriginalsCandidates
test("toOriginalsCandidates: rewrites a preview to /originals/, own ext first", () => {
  const cands = toOriginalsCandidates(
    "https://i.pinimg.com/736x/ab/cd/ef/abcdef0123456789abcdef0123456789.jpg",
  );
  assert.deepEqual(cands, [
    "https://i.pinimg.com/originals/ab/cd/ef/abcdef0123456789abcdef0123456789.jpg",
    "https://i.pinimg.com/originals/ab/cd/ef/abcdef0123456789abcdef0123456789.png",
    "https://i.pinimg.com/originals/ab/cd/ef/abcdef0123456789abcdef0123456789.gif",
    "https://i.pinimg.com/originals/ab/cd/ef/abcdef0123456789abcdef0123456789.webp",
  ]);
});

test("toOriginalsCandidates: keeps a non-jpg source ext at the front, no dupes", () => {
  const cands = toOriginalsCandidates(
    "https://i.pinimg.com/564x/aa/bb/cc/aabbccddeeff00112233445566778899.png",
  );
  assert.equal(cands[0].endsWith(".png"), true);
  assert.equal(new Set(cands).size, cands.length); // png not repeated
  assert.equal(cands.length, 4);
});

test("toOriginalsCandidates: [] for non-pinimg URLs", () => {
  assert.deepEqual(toOriginalsCandidates("https://example.com/x/y.jpg"), []);
  assert.deepEqual(toOriginalsCandidates("https://i.pinimg.com/x/y.svg"), []);
});

// ------------------------------------------------------------- small utilities
test("imageHashFromUrl: extracts the content hash across sizes/queries", () => {
  const h = "abcdef0123456789abcdef0123456789";
  assert.equal(
    imageHashFromUrl(`https://i.pinimg.com/736x/ab/cd/ef/${h}.jpg`),
    h,
  );
  assert.equal(
    imageHashFromUrl(`https://i.pinimg.com/originals/ab/cd/ef/${h}.png?foo=1`),
    h,
  );
  assert.equal(imageHashFromUrl("https://i.pinimg.com/x/short.jpg"), null);
});

test("originalFilenameFromUrl: last path segment", () => {
  assert.equal(
    originalFilenameFromUrl(
      "https://i.pinimg.com/originals/ab/cd/ef/abcdef0123456789abcdef0123456789.png",
    ),
    "abcdef0123456789abcdef0123456789.png",
  );
});

test("sanitizeName: spaces->underscores, illegal chars stripped, collapsed", () => {
  assert.equal(sanitizeName("Clara & Eva vill ha"), "Clara_&_Eva_vill_ha");
  assert.equal(sanitizeName('a/b\\c:d*e?f"g<h>i|j'), "abcdefghij");
  assert.equal(sanitizeName("  hello   world  "), "hello_world");
  assert.equal(sanitizeName("__foo__"), "foo");
});

test("sanitizeName: empty falls back to 'board', length capped, unicode kept", () => {
  assert.equal(sanitizeName(""), "board");
  assert.equal(sanitizeName(null), "board");
  assert.equal(sanitizeName("Mönster fågel"), "Mönster_fågel");
  assert.equal(sanitizeName("x".repeat(200)).length, 80);
});

// -------------------------------------------------------------- badge text
test("progressPercent: 0%, mid, and exactly 100% at completion", () => {
  assert.equal(progressPercent(0, 137), "0%");
  assert.equal(progressPercent(73, 100), "73%");
  assert.equal(progressPercent(137, 137), "100%");
});

test("progressPercent: floored, never a premature 100%", () => {
  // 997/1000 is 99.7% — must read "99%", not "100%". Reaching "100%" must mean
  // every file is actually done.
  assert.equal(progressPercent(997, 1000), "99%");
  assert.equal(progressPercent(1, 3), "33%");
});

test("progressPercent: guards total=0 (no division by zero)", () => {
  assert.equal(progressPercent(0, 0), "0%");
});

test("progressPercent: always fits the ~4-char badge", () => {
  for (const [d, t] of [[0, 9999], [4567, 9999], [9999, 9999], [50, 137]]) {
    assert.ok(progressPercent(d, t).length <= 4, `${d}/${t}`);
  }
});

test("crawlBadgeText: raw count below 10k, abbreviated at/above", () => {
  assert.equal(crawlBadgeText(0), "0");
  assert.equal(crawlBadgeText(42), "42");
  assert.equal(crawlBadgeText(1000), "1000");
  assert.equal(crawlBadgeText(9999), "9999");
  assert.equal(crawlBadgeText(10000), "10k");
  assert.equal(crawlBadgeText(15000), "15k"); // board crawl can reach the 15k cap
});

test("crawlBadgeText: always fits the ~4-char badge", () => {
  for (const n of [0, 9, 99, 999, 9999, 10000, 15000, 600000]) {
    assert.ok(crawlBadgeText(n).length <= 4, `n=${n} -> ${crawlBadgeText(n)}`);
  }
});
