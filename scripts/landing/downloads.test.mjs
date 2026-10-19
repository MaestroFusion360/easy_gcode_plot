import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import { JSDOM } from "jsdom";

const script = fs.readFileSync(
  new URL("../../docs/downloads.js", import.meta.url),
  "utf8",
);
const releaseRoot =
  "https://github.com/MaestroFusion360/easy_gcode_plot/releases/download/v2.9.0/";
const files = [
  "Easy-G-Code-Plot-2.9.0-Windows-x64.exe",
  "easy_gcode_plot_cli.exe",
  "Easy-G-Code-Plot-2.9.0-Linux-x64.tar.gz",
];

for (const language of ["en", "ru"]) {
  for (const outcome of ["published", "unpublished", "offline"]) {
    test(`${language} downloads keep the page version when ${outcome}`, async (t) => {
      const page = language === "ru" ? "ru/index.html" : "index.html";
      const dom = new JSDOM(
        fs.readFileSync(new URL(`../../docs/${page}`, import.meta.url), "utf8"),
        { runScripts: "outside-only" },
      );
      t.after(() => dom.window.close());
      const { window } = dom;
      const links = Array.from(
        window.document.querySelectorAll(
          "[data-windows-download], [data-linux-download]",
        ),
      );
      assert.ok(links.length >= 3);
      const original = links.map((link) => link.href);
      for (const href of original) assert.ok(href.startsWith(releaseRoot));
      const requests = [];
      window.fetch = async (url) => {
        requests.push(url);
        if (outcome === "offline") throw new Error("Offline");
        return {
          ok: outcome === "published",
          json: async () => ({
            assets: files.map((name) => ({
              name,
              browser_download_url: releaseRoot + name,
            })),
          }),
        };
      };
      // Await the actual resolver call without starting a second request.
      await window.eval(script);
      assert.deepEqual(requests, [
        "https://api.github.com/repos/MaestroFusion360/easy_gcode_plot/releases/tags/v2.9.0",
      ]);
      assert.deepEqual(
        links.map((link) => link.href),
        original,
      );
      for (const link of links) {
        const file = link.hasAttribute("data-linux-download")
          ? files[2]
          : link.dataset.windowsDownload === "gui"
            ? files[0]
            : files[1];
        assert.equal(link.href, releaseRoot + file);
      }
    });
  }
}
