import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "parse5";
import postcss from "postcss";
import values from "postcss-value-parser";
import srcset from "parse-srcset";

function elements(node) {
  return [node, ...(node.childNodes || []).flatMap(elements)];
}

export function checkSite(root, { assetsOnly = false } = {}) {
  root = path.resolve(root);
  const errors = [];
  const documents = new Map();
  const visitedCss = new Set();
  const fail = (owner, message) =>
    errors.push(`${path.relative(root, owner)}: ${message}`);

  function local(owner, url) {
    if (!url || /^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(url)) return null;
    const parsed = new URL(url, "https://local.invalid/");
    const pathname = decodeURIComponent(url.split(/[?#]/, 1)[0]);
    const target = pathname.startsWith("/")
      ? path.resolve(root, `.${pathname}`)
      : path.resolve(path.dirname(owner), pathname || path.basename(owner));
    const relative = path.relative(root, target);
    if (relative.startsWith("..") || path.isAbsolute(relative)) {
      fail(owner, `path escapes docs/: ${url}`);
      return null;
    }
    const file =
      fs.existsSync(target) && fs.statSync(target).isDirectory()
        ? path.join(target, "index.html")
        : target;
    if (!fs.existsSync(file) || !fs.statSync(file).isFile()) {
      fail(owner, `missing local resource: ${url}`);
      return null;
    }
    return { file, hash: decodeURIComponent(parsed.hash.slice(1)) };
  }

  function css(owner, text) {
    let sheet;
    try {
      sheet = postcss.parse(text, { from: owner });
    } catch (error) {
      fail(owner, error.message);
      return;
    }
    function references(value) {
      values(value).walk((node) => {
        if (node.type === "function" && node.value.toLowerCase() === "url") {
          const url = values.stringify(node.nodes).replace(/^["']|["']$/g, "");
          resource(owner, url);
        }
      });
    }
    sheet.walkDecls((declaration) => references(declaration.value));
    sheet.walkAtRules("import", (rule) => {
      const first = values(rule.params).nodes[0];
      if (first?.type === "string") resource(owner, first.value);
      else references(rule.params);
    });
  }

  function resource(owner, url) {
    const target = local(owner, url);
    if (
      target &&
      path.extname(target.file) === ".css" &&
      !visitedCss.has(target.file)
    ) {
      visitedCss.add(target.file);
      css(target.file, fs.readFileSync(target.file, "utf8"));
    }
    return target;
  }

  function document(file) {
    if (documents.has(file)) return documents.get(file);
    const nodes = elements(parse(fs.readFileSync(file, "utf8")));
    const ids = new Set();
    for (const node of nodes) {
      const attrs = Object.fromEntries(
        (node.attrs || []).map(({ name, value }) => [name, value]),
      );
      if (attrs.id) {
        if (ids.has(attrs.id) && !assetsOnly)
          fail(file, `duplicate HTML id: ${attrs.id}`);
        ids.add(attrs.id);
      }
    }
    const result = { nodes, ids };
    documents.set(file, result);
    return result;
  }

  // Only published HTML, never source fragments with output-relative URLs.
  function htmlFiles(directory) {
    return fs
      .readdirSync(directory, { withFileTypes: true })
      .flatMap((entry) => {
        const file = path.join(directory, entry.name);
        if (entry.isDirectory())
          return entry.name === "src" ? [] : htmlFiles(file);
        return entry.name.endsWith(".html") ? [file] : [];
      });
  }
  for (const page of ["index.html", "ru/index.html"])
    local(path.join(root, "index.html"), page);
  if (!fs.existsSync(path.join(root, "assets")))
    errors.push(
      "docs/assets/: missing asset directory (restore tracked resources)",
    );
  for (const file of htmlFiles(root)) {
    const { nodes } = document(file);
    for (const node of nodes) {
      const attrs = Object.fromEntries(
        (node.attrs || []).map(({ name, value }) => [name, value]),
      );
      for (const name of ["src", "href", "poster"]) {
        const target = resource(file, attrs[name]);
        if (
          target?.hash &&
          !assetsOnly &&
          path.extname(target.file) === ".html"
        ) {
          if (!document(target.file).ids.has(target.hash))
            fail(file, `missing anchor: ${attrs[name]}`);
        }
      }
      for (const name of ["srcset", "imagesrcset"]) {
        if (attrs[name])
          for (const candidate of srcset(attrs[name]))
            resource(file, candidate.url);
      }
      if (attrs.style) css(file, `x { ${attrs.style} }`);
      if (node.tagName === "style")
        css(
          file,
          (node.childNodes || []).map((child) => child.value || "").join(""),
        );
    }
  }
  return errors;
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const root = fileURLToPath(new URL("../../docs/", import.meta.url));
  const errors = checkSite(root, {
    assetsOnly: process.argv.includes("--assets-only"),
  });
  if (errors.length) {
    console.error(errors.join("\n"));
    process.exitCode = 1;
  } else
    console.log(
      "Landing resources, pages and requested structural checks passed.",
    );
}
