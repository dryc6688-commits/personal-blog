/* ============================================================
   前台交互：代码高亮、一键复制、图片灯箱
   ============================================================ */
(function () {
  "use strict";

  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.top = "-1000px";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) {}
    document.body.removeChild(ta);
  }

  function setupCodeBlocks() {
    if (window.hljs) {
      document.querySelectorAll("pre code").forEach(function (el) {
        if (!el.dataset.highlighted) {
          try { window.hljs.highlightElement(el); } catch (e) {}
        }
      });
    }

    document.querySelectorAll(".prose pre").forEach(function (pre) {
      if (pre.querySelector(".code-copy")) return;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "code-copy";
      btn.textContent = "复制";
      btn.setAttribute("aria-label", "复制代码");
      btn.addEventListener("click", function () {
        var codeEl = pre.querySelector("code");
        var text = codeEl ? codeEl.innerText : pre.innerText;
        var done = function () {
          btn.textContent = "已复制 ✓";
          btn.classList.add("copied");
          if (window.trackEvent) {
            var m = codeEl ? (codeEl.className || "").match(/language-([\w-]+)/) : null;
            window.trackEvent("code_copy", { label: m ? m[1] : "code" });
          }
          setTimeout(function () {
            btn.textContent = "复制";
            btn.classList.remove("copied");
          }, 1600);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, function () {
            fallbackCopy(text);
            done();
          });
        } else {
          fallbackCopy(text);
          done();
        }
      });
      pre.appendChild(btn);
    });
  }

  function setupLightbox() {
    var box = document.getElementById("lightbox");
    if (!box) return;
    var img = document.getElementById("lightbox-img");
    var items = document.querySelectorAll("[data-lightbox]");

    function open(src) {
      img.src = src;
      box.hidden = false;
      document.body.style.overflow = "hidden";
      if (window.trackEvent) window.trackEvent("image_view", { label: src });
    }
    function close() {
      box.hidden = true;
      img.src = "";
      document.body.style.overflow = "";
    }
    items.forEach(function (el) {
      el.addEventListener("click", function () {
        open(el.getAttribute("data-lightbox") || el.querySelector("img").src);
      });
    });
    box.addEventListener("click", function (e) {
      if (e.target === box || e.target.id === "lightbox-close") close();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !box.hidden) close();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupCodeBlocks();
    setupLightbox();
  });
})();
