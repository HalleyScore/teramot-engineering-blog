/*
 * View counts for the Teramot engineering blog.
 *
 * Blowfish ships the markup for this (partials/meta/views.html) but only wires
 * it to Firebase. We use GoatCounter instead: no cookies, no personal data, and
 * nothing for us to operate.
 *
 * The count comes from GoatCounter's public counter endpoint, which needs
 * "Allow adding visitor counts on your website" enabled on the site settings.
 * If no site code is configured, we remove the placeholder rather than leaving
 * it pulsing "loading" forever.
 */
(function () {
  "use strict";

  var PULSE = [
    "animate-pulse",
    "text-transparent",
    "bg-neutral-300",
    "dark:bg-neutral-400",
    "max-h-3",
    "rounded-full",
    "-mt-[2px]",
  ];

  var cfg = {};
  try {
    var el = document.getElementById("engagement-config");
    if (el && el.textContent) cfg = JSON.parse(el.textContent);
  } catch (e) {
    /* malformed config: treated as unconfigured below */
  }

  var code = (cfg.goatcounterCode || "").trim();
  var nodes = document.querySelectorAll("span[id^='views_']");
  if (!nodes.length) return;

  function forEach(list, fn) {
    Array.prototype.forEach.call(list, fn);
  }

  // Each meta item is a <span> wrapper, joined by "&middot;" separator spans.
  // Dropping an item without its separator leaves a stray dot behind.
  function removeMetaItem(node) {
    var wrapper = node.parentElement;
    if (!wrapper) return;
    var sep = wrapper.previousElementSibling;
    if (sep && sep.classList.contains("px-2")) sep.remove();
    else {
      var next = wrapper.nextElementSibling;
      if (next && next.classList.contains("px-2")) next.remove();
    }
    wrapper.remove();
  }

  function settle(node, text) {
    node.textContent = text;
    PULSE.forEach(function (c) {
      node.classList.remove(c);
    });
  }

  if (!code) {
    forEach(nodes, removeMetaItem);
    return;
  }

  // GoatCounter documents the literal path here (yielding a double slash after
  // /counter/), so escape everything except the separators.
  var url =
    "https://" +
    code +
    ".goatcounter.com/counter/" +
    encodeURIComponent(window.location.pathname).replace(/%2F/g, "/") +
    ".json";

  fetch(url, { mode: "cors" })
    .then(function (r) {
      // GoatCounter answers 404 for a path it has never recorded, but still
      // sends a usable {"count":"0"} body. A brand new post has no views yet,
      // so that is a real zero. Anything else is genuinely broken.
      if (!r.ok && r.status !== 404) throw new Error("counter " + r.status);
      return r.json();
    })
    .then(function (d) {
      forEach(nodes, function (n) {
        settle(n, d.count_unique || d.count || "0");
      });
    })
    .catch(function () {
      // Offline, DNS failure, or blocked by an extension: drop the widget
      // rather than showing a number we cannot stand behind.
      forEach(nodes, removeMetaItem);
    });
})();
