// Progressive enhancements: navigation and source links work without JavaScript.
document.documentElement.classList.add("js");

const toggle = document.querySelector(".nav-toggle");
const navigation = document.querySelector("#site-nav");
if (toggle && navigation) {
  toggle.hidden = false;
  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", String(expanded));
    navigation.classList.toggle("is-open", expanded);
  });
  navigation.addEventListener("click", (event) => {
    if (!event.target.closest("a")) return;
    toggle.setAttribute("aria-expanded", "false");
    navigation.classList.remove("is-open");
  });
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape" &&
      toggle.getAttribute("aria-expanded") === "true"
    ) {
      toggle.setAttribute("aria-expanded", "false");
      navigation.classList.remove("is-open");
      toggle.focus();
    }
  });
}

// Links to technical details must open their containing disclosure first.
function revealHashTarget() {
  let id;
  try {
    id = decodeURIComponent(location.hash.slice(1));
  } catch {
    return;
  }
  const target = document.getElementById(id);
  if (!target) return;
  let ancestor = target.parentElement;
  while (ancestor) {
    if (ancestor.tagName === "DETAILS") ancestor.open = true;
    ancestor = ancestor.parentElement;
  }
  target.scrollIntoView({ block: "start" });
}
window.addEventListener("hashchange", revealHashTarget);
document.addEventListener("click", (event) => {
  const link = event.target.closest('a[href^="#"]');
  if (link && link.hash === location.hash) revealHashTarget();
});
if (location.hash) revealHashTarget();

// Existing dimensions reserve image space, including lazy-loaded GIFs.
document.querySelectorAll("a[data-gallery] img").forEach((media) => {
  const frame = media.closest("a");
  function settle() {
    frame.classList.remove("media-loading");
    frame.classList.toggle("media-error", media.naturalWidth === 0);
    frame.removeAttribute("aria-busy");
  }
  media.addEventListener("load", settle, { once: true });
  media.addEventListener("error", settle, { once: true });
  if (media.complete) settle();
  else {
    frame.classList.add("media-loading");
    frame.setAttribute("aria-busy", "true");
  }
});

const viewer = document.querySelector("#image-viewer");
if (viewer && typeof viewer.showModal === "function") {
  const image = viewer.querySelector("img");
  const stage = viewer.querySelector(".viewer-stage");
  const videoPlaceholder = document.createElement("div");
  videoPlaceholder.className = "video-placeholder";
  const caption = viewer.querySelector("#viewer-caption");
  const original = viewer.querySelector(".viewer-original");
  let opener = null;
  let inlineVideo = null;
  document.querySelectorAll("button[data-video-viewer]").forEach((button) => {
    button.hidden = false;
  });

  function openViewer(trigger, title, url) {
    opener = trigger;
    caption.textContent = title;
    original.href = url;
    viewer.showModal();
    document.body.classList.add("viewer-open");
  }

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest(
      "a[data-gallery], [data-video-viewer]",
    );
    if (
      !trigger ||
      event.button !== 0 ||
      event.ctrlKey ||
      event.metaKey ||
      event.shiftKey ||
      event.altKey
    )
      return;
    if (trigger.hasAttribute("data-video-viewer")) {
      const source = document.querySelector(".video-preview video");
      const url = source?.currentSrc || source?.querySelector("source")?.src;
      if (!source || !url) return;
      event.preventDefault();
      inlineVideo = source;
      source.pause();
      image.hidden = true;
      videoPlaceholder.style.aspectRatio = `${source.width} / ${source.height}`;
      source.replaceWith(videoPlaceholder);
      stage.append(source);
      openViewer(trigger, source.getAttribute("aria-label") || "", url);
      // The click explicitly requests playback; reduced-motion never autoplays.
      source.play().catch(() => {});
      return;
    }
    const source = trigger.querySelector("img");
    if (!source) return;
    event.preventDefault();
    image.hidden = false;
    image.src = trigger.href;
    image.alt = source.alt;
    openViewer(trigger, source.alt, trigger.href);
  });
  viewer
    .querySelector(".viewer-close")
    .addEventListener("click", () => viewer.close());
  viewer.addEventListener("close", () => {
    document.body.classList.remove("viewer-open");
    if (inlineVideo) {
      inlineVideo.pause();
      videoPlaceholder.replaceWith(inlineVideo);
      inlineVideo = null;
    }
    image.removeAttribute("src");
    image.hidden = true;
    opener?.focus({ preventScroll: true });
    opener = null;
  });
}
