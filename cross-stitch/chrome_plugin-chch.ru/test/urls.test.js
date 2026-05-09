import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  parseGalleryUrl,
  sizeRank,
  pickFullSizeForPhoto,
  extractOriginalUrl,
  extractPostedDate,
  sanitizeFolderName,
  originalFilenameFromUrl,
} from "../urls.js";

const fixture = (name) =>
  readFileSync(fileURLToPath(new URL(`./fixtures/${name}`, import.meta.url)), "latin1");

test("parseGalleryUrl extracts the structured parts", () => {
  const url = "https://data31.chch.ru/albums/gallery/372752-a651b-105637575-200-ub8995.jpg";
  assert.deepEqual(parseGalleryUrl(url), {
    albumId: "372752",
    midHash: "a651b",
    photoId: "105637575",
    size: "200",
    trailingHash: "ub8995",
    ext: "jpg",
    url,
  });
});

test("parseGalleryUrl handles m{W}x{H} and src size variants", () => {
  assert.equal(
    parseGalleryUrl("https://data31.chch.ru/albums/gallery/372752-78385-105637575-m750x740-ub8995.jpg").size,
    "m750x740",
  );
  assert.equal(
    parseGalleryUrl("https://data31.chch.ru/albums/gallery/372752-1c09a-105637575-src-ub8995.jpg").size,
    "src",
  );
});

test("parseGalleryUrl handles the empty-size 'Original' variant (double-dash)", () => {
  // The zoom=8 page exposes original-resolution URLs with no size segment.
  const parsed = parseGalleryUrl(
    "https://data31.chch.ru/albums/gallery/372752-cbcdb-105637575--ub8995.jpg",
  );
  assert.equal(parsed.size, "");
  assert.equal(parsed.photoId, "105637575");
  assert.equal(parsed.trailingHash, "ub8995");
});

test("parseGalleryUrl returns null on non-gallery URLs", () => {
  assert.equal(parseGalleryUrl("https://example.com/foo.jpg"), null);
  assert.equal(parseGalleryUrl("https://data2.chch.ru/albums/upicg/372752-22a3e-435893-c50-crop.jpg"), null);
});

test("sizeRank: m{W}x{H} beats pixel-width thumbs (matrix is the real photo)", () => {
  assert.ok(sizeRank("m200x200") > sizeRank("4000"));
  assert.ok(sizeRank("m750x740") > sizeRank("m549x500"));
});

test("sizeRank: pixel widths compared numerically", () => {
  assert.ok(sizeRank("400") > sizeRank("200"));
});

test("sizeRank: src is deliberately ranked low — chch.ru gates it with a placeholder", () => {
  assert.ok(sizeRank("src") < sizeRank("m100x100"));
  assert.ok(sizeRank("src") < sizeRank("100"));
});

test("sizeRank: unknown / cropped segments rank lowest", () => {
  assert.ok(sizeRank("c80") < sizeRank("100"));
  assert.ok(sizeRank("anything") < sizeRank("50"));
});

test("pickFullSizeForPhoto picks the largest m{W}x{H} from the real photo page", () => {
  // The real photo page exposes 100/200/400/c80/m549x500/m750x740/src for one
  // photoId. We want m750x740 — the largest reliable variant.
  const html = fixture("photo_page_sample.html");
  const url = pickFullSizeForPhoto(html, "105637575");
  assert.match(url, /-105637575-m750x740-/);
});

test("pickFullSizeForPhoto picks largest matrix size", () => {
  const html = `
    <a href="https://data1.chch.ru/albums/gallery/372752-aaaaa-999-200-u11111.jpg">a</a>
    <a href="https://data1.chch.ru/albums/gallery/372752-bbbbb-999-m400x300-u22222.jpg">b</a>
    <a href="https://data1.chch.ru/albums/gallery/372752-ccccc-999-m800x600-u33333.jpg">c</a>
  `;
  const url = pickFullSizeForPhoto(html, "999");
  assert.match(url, /-m800x600-/);
});

test("pickFullSizeForPhoto falls back to pixel width when no matrix size exists", () => {
  const html = `
    https://data1.chch.ru/albums/gallery/372752-aaaaa-555-100-u11111.jpg
    https://data1.chch.ru/albums/gallery/372752-bbbbb-555-400-u22222.jpg
  `;
  assert.match(pickFullSizeForPhoto(html, "555"), /-400-/);
});

test("pickFullSizeForPhoto ignores other photo IDs on the same page", () => {
  const html = `
    https://data1.chch.ru/albums/gallery/372752-aaaaa-111-src-u11111.jpg
    https://data1.chch.ru/albums/gallery/372752-bbbbb-222-src-u22222.jpg
  `;
  assert.match(pickFullSizeForPhoto(html, "111"), /-111-src-/);
  assert.match(pickFullSizeForPhoto(html, "222"), /-222-src-/);
  assert.equal(pickFullSizeForPhoto(html, "333"), null);
});

test("pickFullSizeForPhoto returns null when nothing matches", () => {
  assert.equal(pickFullSizeForPhoto("<html>nothing here</html>", "12345"), null);
});

test("extractOriginalUrl finds the empty-size variant on a real zoom=8 page", () => {
  const html = fixture("zoom_page_sample.html");
  const url = extractOriginalUrl(html, "105637575");
  assert.match(url, /-105637575--/);
  assert.ok(url.endsWith(".jpg"));
});

test("extractOriginalUrl returns null when the photoId isn't on the page", () => {
  const html = fixture("zoom_page_sample.html");
  assert.equal(extractOriginalUrl(html, "9999999999"), null);
});

test("extractOriginalUrl ignores other size variants", () => {
  // No double-dash -> not the original.
  const html = `
    https://data1.chch.ru/albums/gallery/372752-aaa-555-m750x740-u11111.jpg
    https://data1.chch.ru/albums/gallery/372752-bbb-555-200-u22222.jpg
  `;
  assert.equal(extractOriginalUrl(html, "555"), null);
});

test("extractOriginalUrl scopes to the right photoId on a multi-photo page", () => {
  const html = `
    https://data1.chch.ru/albums/gallery/372752-aaaaa-111--u11111.jpg
    https://data1.chch.ru/albums/gallery/372752-bbbbb-222--u22222.jpg
  `;
  assert.match(extractOriginalUrl(html, "111"), /-111--/);
  assert.match(extractOriginalUrl(html, "222"), /-222--/);
});

test("sanitizeFolderName: spaces become underscores", () => {
  assert.equal(sanitizeFolderName("Eva Rosenstad"), "Eva_Rosenstad");
});

test("sanitizeFolderName: strips Windows-illegal characters", () => {
  assert.equal(sanitizeFolderName('a/b\\c:d*e?f"g<h>i|j'), "abcdefghij");
});

test("sanitizeFolderName: collapses runs of underscores and trims edges", () => {
  assert.equal(sanitizeFolderName("  hello   world  "), "hello_world");
  assert.equal(sanitizeFolderName("__foo__"), "foo");
});

test("sanitizeFolderName: empty / null falls back to 'album'", () => {
  assert.equal(sanitizeFolderName(""), "album");
  assert.equal(sanitizeFolderName(null), "album");
  assert.equal(sanitizeFolderName(undefined), "album");
});

test("sanitizeFolderName: cyrillic is preserved", () => {
  assert.equal(sanitizeFolderName("Альбом фото"), "Альбом_фото");
});

test("sanitizeFolderName: caps at 80 chars to keep filesystem-friendly", () => {
  const long = "x".repeat(200);
  assert.equal(sanitizeFolderName(long).length, 80);
});

test("originalFilenameFromUrl: pulls last path segment", () => {
  assert.equal(
    originalFilenameFromUrl("https://data31.chch.ru/albums/gallery/372752-78385-105637575-m750x740-ub8995.jpg"),
    "372752-78385-105637575-m750x740-ub8995.jpg",
  );
});

test("extractPostedDate finds the date in a real main_body subpanel response", () => {
  const json = readFileSync(
    fileURLToPath(new URL("./fixtures/main_body_sample.json", import.meta.url)),
    "latin1",
  );
  assert.equal(extractPostedDate(json), "2018-01-27");
});

test("extractPostedDate matches both ?day= and &day= forms", () => {
  assert.equal(extractPostedDate('href="/?p=calendar&day=2020-12-31"'), "2020-12-31");
  assert.equal(extractPostedDate('href="/calendar?day=2020-12-31&u=1"'), "2020-12-31");
});

test("extractPostedDate returns null when there's no day= param", () => {
  assert.equal(extractPostedDate('<p>some unrelated content 2020-12-31</p>'), null);
  assert.equal(extractPostedDate(""), null);
});

test("extractPostedDate ignores partial / malformed date params", () => {
  assert.equal(extractPostedDate("?day=2020-1-31"), null);
  assert.equal(extractPostedDate("?day=2020-12-3"), null);
  assert.equal(extractPostedDate("?dayofweek=2020-12-31"), null);
});
