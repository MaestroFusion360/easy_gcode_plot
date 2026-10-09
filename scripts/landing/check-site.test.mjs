import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { checkSite } from "./check-site.mjs";

function fixture(t, html = "") {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "landing-assets-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, "ru"));
  fs.mkdirSync(path.join(root, "assets"));
  fs.writeFileSync(path.join(root, "index.html"), html);
  fs.writeFileSync(path.join(root, "ru/index.html"), "");
  return root;
}

test("both published languages and all local report assets exist", () => {
  assert.deepEqual(
    checkSite(fileURLToPath(new URL("../../docs/", import.meta.url))),
    [],
  );
});

test("missing HTML and CSS resources include the owner and path", (t) => {
  const root = fixture(
    t,
    '<link href="broken.css"><video poster="missing-poster.jpg"><source src="missing.mp4"></video><img srcset="missing.png 1x, missing2.png 2x"><script src="missing.js"></script>',
  );
  fs.writeFileSync(
    path.join(root, "broken.css"),
    'p { background: url("missing.gif"); }',
  );
  fs.writeFileSync(
    path.join(root, "ru/index.html"),
    '<img src="assets/wrong-relative.png">',
  );
  const errors = checkSite(root, { assetsOnly: true });
  for (const resource of [
    "missing-poster.jpg",
    "missing.mp4",
    "missing.png",
    "missing2.png",
    "missing.js",
    "missing.gif",
    "assets/wrong-relative.png",
  ]) {
    assert.ok(
      errors.some((error) => error.includes(resource)),
      resource,
    );
  }
  assert.ok(errors.some((error) => error.startsWith("broken.css:")));
  assert.ok(
    errors.some((error) =>
      error.startsWith(path.join("ru", "index.html") + ":"),
    ),
  );
});

test("missing assets directory is an error rather than a skipped check", (t) => {
  const root = fixture(t);
  fs.rmdirSync(path.join(root, "assets"));
  assert.ok(
    checkSite(root).some((error) => error.includes("missing asset directory")),
  );
});

test("duplicate ids and broken cross-language anchors fail", (t) => {
  const root = fixture(
    t,
    '<p id="same"></p><p id="same"></p><a href="ru/index.html#missing">RU</a>',
  );
  const errors = checkSite(root);
  assert.ok(errors.some((error) => error.includes("duplicate HTML id: same")));
  assert.ok(
    errors.some((error) =>
      error.includes("missing anchor: ru/index.html#missing"),
    ),
  );
});

test("external, data and queried local resources are handled without network access", (t) => {
  const root = fixture(
    t,
    '<script src="https://invalid.invalid/a.js"></script><img src="data:image/png;base64,AAAA"><a href="index.html?v=1#main">Home</a><p id="main"></p>',
  );
  assert.deepEqual(checkSite(root), []);
});
