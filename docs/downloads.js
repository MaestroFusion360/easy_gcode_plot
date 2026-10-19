// Resolve assets for the version described by the page.
// Preserve its versioned links when the API is unavailable.
async function resolveDownloads() {
  const links = document.querySelectorAll(
    "[data-windows-download], [data-linux-download]",
  );
  if (!links.length) return;

  const version = document.querySelector('meta[name="app-version"]')?.content;
  const release = version ? `tags/v${encodeURIComponent(version)}` : "latest";

  try {
    const response = await fetch(
      `https://api.github.com/repos/MaestroFusion360/easy_gcode_plot/releases/${release}`,
      { headers: { Accept: "application/vnd.github+json" } },
    );
    if (!response.ok) return;
    const releaseData = await response.json();
    if (!Array.isArray(releaseData.assets)) return;

    const gui = releaseData.assets.find((asset) =>
      /^Easy-G-Code-Plot-.+-Windows-x64\.exe$/i.test(asset.name),
    );
    const cli = releaseData.assets.find(
      (asset) => asset.name === "easy_gcode_plot_cli.exe",
    );
    const linux = releaseData.assets.find((asset) =>
      /^Easy-G-Code-Plot-.+-Linux-x64\.tar\.gz$/i.test(asset.name),
    );

    for (const link of links) {
      const asset = link.dataset.linuxDownload
        ? linux
        : link.dataset.windowsDownload === "gui"
          ? gui
          : cli;
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

resolveDownloads();
