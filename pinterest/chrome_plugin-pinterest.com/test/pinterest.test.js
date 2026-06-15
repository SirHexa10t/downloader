import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  parseBoardUrl,
  buildDataParam,
  buildResourceUrl,
  boardResourceOptions,
  boardFeedOptions,
  boardFromResponse,
  pinsFromResponse,
  nextBookmark,
  pickPinImage,
  toOriginalsCandidates,
  imageHashFromUrl,
  originalFilenameFromUrl,
  sanitizeName,
} from "../pinterest.js";

const fixture = (name) =>
  JSON.parse(
    readFileSync(fileURLToPath(new URL(`./fixtures/${name}`, import.meta.url))),
  );

// ---------------------------------------------------------------- parseBoardUrl
test("parseBoardUrl: parses a country-subdomain board URL", () => {
  const b = parseBoardUrl("https://se.pinterest.com/enfald/clara-eva-vill-ha/");
  assert.deepEqual(b, {
    origin: "https://se.pinterest.com",
    username: "enfald",
    slug: "clara-eva-vill-ha",
    boardPath: "/enfald/clara-eva-vill-ha/",
    sectionSlug: null,
  });
});

test("parseBoardUrl: www and apex hosts, trailing slash optional, query ignored", () => {
  assert.equal(
    parseBoardUrl("https://www.pinterest.com/enfald/clara-eva-vill-ha").slug,
    "clara-eva-vill-ha",
  );
  assert.equal(
    parseBoardUrl("https://pinterest.com/enfald/clara-eva-vill-ha/?invite=1")
      .username,
    "enfald",
  );
});

test("parseBoardUrl: a third path segment is a section -> resolves to parent board", () => {
  const b = parseBoardUrl(
    "https://www.pinterest.com/enfald/clara-eva-vill-ha/klara/",
  );
  assert.equal(b.slug, "clara-eva-vill-ha");
  assert.equal(b.boardPath, "/enfald/clara-eva-vill-ha/");
  assert.equal(b.sectionSlug, "klara");
});

test("parseBoardUrl: rejects bare profiles, pin pages, and app routes", () => {
  assert.equal(parseBoardUrl("https://www.pinterest.com/enfald/"), null); // profile
  assert.equal(parseBoardUrl("https://www.pinterest.com/pin/12345/"), null); // pin
  assert.equal(parseBoardUrl("https://www.pinterest.com/search/pins/?q=x"), null);
  assert.equal(parseBoardUrl("https://www.pinterest.com/"), null); // home
});

test("parseBoardUrl: rejects profile tabs (_saved / _created)", () => {
  assert.equal(parseBoardUrl("https://www.pinterest.com/enfald/_saved/"), null);
  assert.equal(parseBoardUrl("https://www.pinterest.com/enfald/_created/"), null);
});

test("parseBoardUrl: accepts country ccTLDs and country subdomains", () => {
  for (const host of [
    "www.pinterest.co.uk",
    "pinterest.com.au",
    "pinterest.se",
    "pinterest.fr",
    "uk.pinterest.com", // country subdomain
  ]) {
    const b = parseBoardUrl(`https://${host}/enfald/clara-eva-vill-ha/`);
    assert.equal(b?.slug, "clara-eva-vill-ha", `expected board for ${host}`);
    assert.equal(b.origin, `https://${host}`);
  }
});

test("parseBoardUrl: rejects non-Pinterest hosts (incl. lookalikes)", () => {
  assert.equal(parseBoardUrl("https://example.com/enfald/board/"), null);
  assert.equal(parseBoardUrl("https://notpinterest.com/enfald/board/"), null);
  assert.equal(parseBoardUrl("https://pinterest.com.evil.com/a/b/"), null);
  assert.equal(parseBoardUrl("not a url"), null);
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
