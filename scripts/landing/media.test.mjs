import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import { JSDOM } from "jsdom";
import postcss from "postcss";

const script = fs.readFileSync(
  new URL("../../docs/site.js", import.meta.url),
  "utf8",
);

function page(t, language) {
  const name = language === "ru" ? "ru/index.html" : "index.html";
  const dom = new JSDOM(
    fs.readFileSync(new URL(`../../docs/${name}`, import.meta.url), "utf8"),
    {
      url: `https://example.test/easy_gcode_plot/${name}`,
      runScripts: "outside-only",
    },
  );
  t.after(() => dom.window.close());
  const { window } = dom;
  const video = window.document.querySelector(".video-preview video");
  let paused = true;
  let playCalls = 0;
  Object.defineProperty(video, "paused", { get: () => paused });
  video.play = () => {
    paused = false;
    playCalls++;
    return Promise.resolve();
  };
  video.pause = () => {
    paused = true;
  };
  const dialog = window.document.querySelector("dialog");
  dialog.showModal = () => {
    dialog.open = true;
  };
  dialog.close = () => {
    dialog.open = false;
    dialog.dispatchEvent(new window.Event("close"));
  };
  return { window, video, dialog, playCalls: () => playCalls };
}

test("reduced motion disables skeleton animation and never starts video", (t) => {
  const { window, playCalls } = page(t, "en");
  window.matchMedia = () => ({ matches: true });
  window.eval(script);
  assert.equal(playCalls(), 0);
  const sheet = postcss.parse(
    fs.readFileSync(new URL("../../docs/styles.css", import.meta.url), "utf8"),
  );
  let disabled = false;
  sheet.walkAtRules("media", (rule) => {
    if (rule.params === "(prefers-reduced-motion: reduce)") {
      rule.walkDecls("animation", (declaration) => {
        disabled ||= declaration.value === "none" && declaration.important;
      });
    }
  });
  assert.equal(disabled, true);
});

for (const language of ["en", "ru"]) {
  test(`${language}: explicit playback reuses one video and closing always stops it`, (t) => {
    const { window, video, dialog, playCalls } = page(t, language);
    const document = window.document;
    assert.equal(video.autoplay, false);
    assert.equal(video.preload, "none");
    assert.ok(video.poster.endsWith("easy_gcode_plot-poster.jpg"));
    video.currentTime = 12;
    video.volume = 0.4;
    video.playbackRate = 1.5;
    window.eval(script);
    assert.equal(playCalls(), 0);
    const originalSource = video.querySelector("source").src;
    const trigger = document.querySelector("button[data-video-viewer]");
    trigger.click();
    assert.equal(dialog.open, true);
    assert.equal(dialog.querySelector("video"), video);
    assert.equal(document.querySelectorAll("video").length, 1);
    assert.equal(playCalls(), 1);
    assert.equal(video.querySelector("source").src, originalSource);
    assert.equal(video.currentTime, 12);
    assert.equal(video.volume, 0.4);
    assert.equal(video.playbackRate, 1.5);
    document.querySelector(".viewer-close").click();
    assert.equal(video.paused, true);
    assert.equal(document.querySelector(".video-preview video"), video);
    assert.equal(document.activeElement, trigger);
    trigger.click();
    dialog.close(); // Native Escape also dispatches close.
    assert.equal(video.paused, true);
    assert.equal(playCalls(), 2);
  });

  test(`${language}: lazy image and GIF loading, errors and cached images settle`, (t) => {
    const { window } = page(t, language);
    const media = [...window.document.querySelectorAll("a[data-gallery] img")];
    const image = media[0];
    const broken = media[1];
    const cached = media[2];
    const sources = media.map((item) => item.src);
    Object.defineProperty(image, "complete", { value: false });
    Object.defineProperty(broken, "complete", { value: false });
    Object.defineProperty(cached, "complete", { value: true });
    Object.defineProperty(cached, "naturalWidth", { value: 1280 });
    window.eval(script);
    assert.ok(image.closest("a").classList.contains("media-loading"));
    assert.equal(image.closest("a").getAttribute("aria-busy"), "true");
    Object.defineProperty(image, "naturalWidth", { value: 1280 });
    image.dispatchEvent(new window.Event("load"));
    broken.dispatchEvent(new window.Event("error"));
    assert.equal(image.closest("a").classList.contains("media-loading"), false);
    assert.equal(
      broken.closest("a").classList.contains("media-loading"),
      false,
    );
    assert.equal(broken.closest("a").classList.contains("media-error"), true);
    assert.equal(
      cached.closest("a").classList.contains("media-loading"),
      false,
    );
    assert.equal(cached.closest("a").classList.contains("media-error"), false);
    assert.deepEqual(
      media.map((item) => item.src),
      sources,
    );
    for (const item of media) {
      assert.ok(
        item.width > 0 && item.height > 0,
        "dimensions reserve layout space",
      );
    }
    assert.equal(
      window.document
        .querySelector(".brand img")
        .closest("a")
        .classList.contains("media-loading"),
      false,
    );
  });
}
