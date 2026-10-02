# Publishing the landing page

The English page is `index.html`; the Russian page is `ru/index.html`. Both
share `styles.css` and the images in `assets/`. There is no build step,
JavaScript framework dependency or Jekyll configuration. `.nojekyll` disables Jekyll.

The landing page is a compact technical overview of Easy G-Code Plot. It
is intentionally not a replacement for `FAQ.md` / `FAQ_RU.md`: exact command
semantics, diagnostics, controller limits, CLI options and export contracts
belong in the FAQ.

## Preview

Open either HTML file in a browser, or run from the repository root:

```sh
python -m http.server 8000 --directory docs
```

Visit `http://localhost:8000/` and `http://localhost:8000/ru/`.

## GitHub Pages

After committing and pushing the files yourself, open the repository's
**Settings → Pages**. Under **Build and deployment**, select:

- **Source:** Deploy from a branch
- **Branch:** `main`
- **Folder:** `/docs`

Save the settings and wait for GitHub's Pages deployment. The expected address is
`https://maestrofusion360.github.io/easy_gcode_plot/`; Russian is at `/ru/`.
No custom workflow YAML is needed. This change does not activate or publish Pages.

## Maintenance

Update both languages together. Keep capability descriptions aligned with
`FAQ.md` / `FAQ_RU.md` and the release documentation. Do not advertise planned
features as current functionality. Controller-specific features should appear in
the general capability model rather than as separate marketing sections.

Windows download buttons resolve the GUI and CLI asset URLs from the latest
GitHub release through `downloads.js`. If the API is unavailable, the GUI link
opens the latest release page; the CLI link uses GitHub's latest-asset redirect. All landing-page screenshots and animations live in
`docs/assets/`.

## Local assets

The project logo is copied from `app/resources/icons/logo.svg` to
`assets/logo.svg`, which is also used as the favicon. Keep these files in sync.

Onest is served from `assets/fonts/Onest.ttf` and includes Latin and Cyrillic
characters. Its SIL Open Font License is included in `assets/fonts/OFL.txt`.
Source: https://github.com/google/fonts/tree/main/ofl/onest. No external font
service or build step is required; relative asset paths work under the GitHub
Pages repository subdirectory and in a local preview.
