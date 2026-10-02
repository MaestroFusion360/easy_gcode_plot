// Resolve the versioned Windows GUI asset without hard-coding a release tag.
// The latest release page remains usable if the API is unavailable.
async function resolveWindowsDownloads() {
  const links = document.querySelectorAll("[data-windows-download]");
  if (!links.length) return;

  try {
    const response = await fetch(
      "https://api.github.com/repos/MaestroFusion360/easy_gcode_plot/releases/latest",
      { headers: { Accept: "application/vnd.github+json" } },
    );
    if (!response.ok) return;
    const release = await response.json();
    if (!Array.isArray(release.assets)) return;

    const gui = release.assets.find((asset) =>
      /^Easy-G-Code-Plot-.+-Windows-x64\.exe$/i.test(asset.name),
    );
    const cli = release.assets.find(
      (asset) => asset.name === "easy_gcode_plot_cli.exe",
    );

    for (const link of links) {
      const asset = link.dataset.windowsDownload === "gui" ? gui : cli;
      if (!asset) continue;
      const url = new URL(asset.browser_download_url);
      if (
        url.origin !== "https://github.com" ||
        !url.pathname.startsWith(
          "/MaestroFusion360/easy_gcode_plot/releases/download/",
        )
      )
        continue;
      link.href = url.href;
    }
  } catch {
    // Preserve the normal links when offline or rate-limited.
  }
}

resolveWindowsDownloads();
