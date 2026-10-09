# Publishing the landing page

The published English page is [https://maestrofusion360.github.io/easy_gcode_plot/](https://maestrofusion360.github.io/easy_gcode_plot/);
Russian is [https://maestrofusion360.github.io/easy_gcode_plot/ru/](https://maestrofusion360.github.io/easy_gcode_plot/ru/).

The English output is `index.html`; the Russian output is `ru/index.html`.
Editable HTML lives in `src/en/` and `src/ru/`, with matching section names.
Both pages share `styles.css`, `site.js`, `downloads.js` and the images in `assets/`.
Python assembles the HTML locally; there is no JavaScript framework dependency,
browser-side fragment loading or Jekyll configuration. `.nojekyll` disables Jekyll.

The landing page is a compact technical overview of Easy G-Code Plot. It
is intentionally not a replacement for [FAQ.md](../FAQ.md) / [FAQ_RU.md](../FAQ_RU.md): exact command
semantics, diagnostics, controller limits, CLI options and export contracts
belong in the FAQ.

## Preview

After editing fragments, regenerate both pages from the repository root:

```sh
python docs/build.py
```

Open either generated HTML file in a browser, or serve `docs`:

```sh
python -m http.server 8000 --directory docs
```

Visit `http://localhost:8000/` and `http://localhost:8000/ru/`.

Check that the generated pages match their sources without changing files:

```sh
python docs/build.py --check
```

## GitHub Pages

After committing and pushing the files yourself, open the repository's
**Settings → Pages**. Under **Build and deployment**, select:

- **Source:** Deploy from a branch
- **Branch:** `main`
- **Folder:** `/docs`

Save the settings and wait for GitHub's Pages deployment. The expected address is
`https://maestrofusion360.github.io/easy_gcode_plot/`; Russian is at `/ru/`.
No custom workflow YAML is needed. This change does not activate or publish Pages.

## Landing quality checks

From the repository root, use Node.js 22.13+ and Python 3:

```sh
npm ci
npm run check
```

`npm run check` runs ESLint, Stylelint, Prettier, `python docs/build.py --check`,
local resource/anchor/duplicate-ID checks, and the Node DOM and checker regressions.
Browser playback and visual layout still need a real browser; DOM tests do not
decode video or measure CLS.

- `npm run lint`: browser JavaScript and shared CSS correctness.
- `npm run format:check`: formatting of editable landing files and tooling.
- `npm run format`: format those sources and regenerate both pages.
- `npm run test:assets`: check published HTML and referenced local files without network requests.
- `npm test`: exercise missing-resource detection and media loading/playback behavior.

Generated pages, the example report and comparison Markdown content are excluded
from Prettier. Keep `package-lock.json` committed. Stylelint's recommended rules
are used with only the ordering rule `no-descending-specificity` disabled: the
existing component sections deliberately retain their cascade order.

Video previews use a real frame poster and `preload="none"`, with no autoplay.
An explicit preview click moves the same video element into the dialog, retaining
time, volume and speed; closing pauses it and restores it to the page. Native
controls remain available. Reduced-motion preferences never initiate playback.
Gallery images and GIFs reserve space using their existing dimensions. JavaScript
shows a CSS skeleton until load or error; cached images settle immediately. Error
states stop the animation, and reduced-motion disables skeleton animation.

## Maintenance

Edit the fragments rather than the generated `index.html` files:

- `src/en/index.html` / `src/ru/index.html`: metadata, asset paths and section order.
- `header.html`, `hero.html`, `footer.html`: navigation, introduction and footer.
- `capabilities.html`: command section layout; `controllers/` contains separate
  FANUC turning, FANUC milling, SINUMERIK ISO-M and native tables.
- `visualization.html`: 3D playback, STL models, turning stock removal and rotary demonstrations.
- `tools.html` and `generators.html`: tool library/editor screenshots and all four hole/pocket generator screenshots.
- `export.html`, `execution.html`, `statistics.html`, `automation.html` and `documentation.html`: the corresponding feature sections.
- `comparison.html`: the collapsible comparison wrapper. `COMPARISON.md` (English) and `COMPARISON_RU.md` (Russian) are the comparison content sources; `comparison.py` renders their supported Markdown subset during assembly.
- `site.js`: progressive mobile navigation, opening deep-linked disclosures and a keyboard-accessible image/video dialog covering the viewport. Without JavaScript, navigation, disclosures and original-image links remain usable.
- `styles.css`: shared appearance; `downloads.js`: release download links.

Includes use `<!-- include: relative/file.html -->` on a separate line. They are
expanded relative to the including file. `<!-- comparison: en -->` / `<!-- comparison: ru -->` embeds the corresponding Markdown comparison at build time, without a browser fetch. Run `python docs/build.py` and commit
both the edited sources and generated pages. Assembly uses only the Python
standard library; no additional environment or package installation is needed.
GitHub Pages continues serving the checked-in output without a build workflow.

Update both languages together. Keep capability descriptions aligned with
`FAQ.md` / `FAQ_RU.md` and the release documentation. Do not advertise planned
features as current functionality. Controller-specific features should appear in
the general capability model rather than as separate marketing sections.

Windows download buttons resolve the GUI and CLI asset URLs from the latest
GitHub release through `downloads.js`. If the API is unavailable, the GUI link
opens the latest release page; the CLI link uses GitHub's latest-asset redirect. All landing-page screenshots and animations live in
`docs/assets/`. Keep screenshots next to their related feature, with an accurate caption and actual image dimensions; do not restore a separate mixed gallery. Both pages use the same asset filenames and relative links, including under the GitHub Pages repository path.

## Local assets

`assets/` is tracked in this repository and served directly by GitHub Pages.
There is no automatic asset download or generation during HTML assembly. If an
archive omits it, restore the real directory from the repository before checking
or publishing; `npm run test:assets` intentionally fails when it is absent.
The video poster can be regenerated from the existing cropped MP4:

```sh
ffmpeg -ss 5 -i docs/assets/easy_gcode_plot.mp4 -frames:v 1 -q:v 3 -update 1 docs/assets/easy_gcode_plot-poster.jpg
```

The project logo is copied from `app/resources/icons/logo.svg` to
`assets/logo.svg`, which is also used as the favicon. Keep these files in sync.

Onest is served from `assets/fonts/Onest.ttf` and includes Latin and Cyrillic
characters. Its SIL Open Font License is included in `assets/fonts/OFL.txt`.
Source: https://github.com/google/fonts/tree/main/ofl/onest. No external font
service or build step is required; relative asset paths work under the GitHub
Pages repository subdirectory and in a local preview.
