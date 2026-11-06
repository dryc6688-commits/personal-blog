/* ============================================================
   前端埋点
   上报：页面访问 / 文章点击 / 分类点击 / 视频播放
   音乐播放、代码复制、图片查看分别在 player.js、main.js 中上报
   ============================================================ */
(function () {
  "use strict";

  var path = location.pathname;
  if (path.indexOf("/admin") === 0 || path.indexOf("/static") === 0) return;
  if (navigator.doNotTrack === "1" || window.doNotTrack === "1") return;

  function currentPostId() {
    var m = path.match(/^\/post\/(\d+)/);
    return m ? parseInt(m[1], 10) : null;
  }

  function send(event, data) {
    var payload = {
      event: event,
      path: location.pathname + location.search,
      post_id: currentPostId(),
      referer: document.referrer || ""
    };
    if (data) {
      for (var k in data) {
        if (Object.prototype.hasOwnProperty.call(data, k)) payload[k] = data[k];
      }
    }
    var body;
    try {
      body = JSON.stringify(payload);
      if (navigator.sendBeacon) {
        var blob = new Blob([body], { type: "application/json" });
        if (navigator.sendBeacon("/api/track", blob)) return;
      }
    } catch (e) {}
    try {
      fetch("/api/track", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body,
        keepalive: true
      });
    } catch (e) {}
  }

  window.trackEvent = send;

  // 页面访问
  send("pageview");

  // 文章卡片 / 分类点击
  document.addEventListener("click", function (e) {
    var node = e.target;
    if (!node || !node.closest) return;

    var card = node.closest(".post-card");
    if (card) {
      var pid = parseInt(card.getAttribute("data-post-id") || "0", 10) || null;
      var titleEl = card.querySelector(".card-title");
      send("article_click", {
        post_id: pid,
        label: titleEl ? titleEl.textContent.trim() : ""
      });
      return;
    }

    var cat = node.closest(".cat-pill, .category-chip");
    if (cat) {
      var href = cat.getAttribute("href") || "";
      var m = href.match(/[?&]category=(\d+)/);
      send("category_click", {
        category_id: m ? parseInt(m[1], 10) : null,
        label: cat.textContent.trim()
      });
    }
  }, true);

  // 视频播放（视频播放事件不冒泡，用捕获）
  document.addEventListener("play", function (e) {
    var t = e.target;
    if (t && t.tagName === "VIDEO") {
      send("video_play", {
        label: (t.currentSrc || t.getAttribute("src") || "").slice(0, 200)
      });
    }
  }, true);
})();
