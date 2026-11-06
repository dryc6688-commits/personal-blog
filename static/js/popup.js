/* 站点弹窗：图片 / 内容点击跳转 + 手动关闭 / 点击外部关闭 + 自动关闭倒计时 */
(function () {
  "use strict";

  var cfgEl = document.getElementById("popup-config");
  if (!cfgEl) return;
  var cfg;
  try { cfg = JSON.parse(cfgEl.textContent); } catch (e) { return; }
  if (!cfg || !cfg.enabled) return;

  var box = document.getElementById("site-popup");
  if (!box) return;
  var closeBtn = document.getElementById("site-popup-close");
  var countdownEl = document.getElementById("site-popup-countdown");
  var KEY = "blog_popup_last";
  var timer = null;

  function today() {
    var d = new Date();
    return d.getFullYear() + "-" +
      String(d.getMonth() + 1).padStart(2, "0") + "-" +
      String(d.getDate()).padStart(2, "0");
  }
  function lastDate() {
    try { return localStorage.getItem(KEY) || ""; } catch (e) { return ""; }
  }
  function mark() {
    try { localStorage.setItem(KEY, today()); } catch (e) {}
  }
  function clearTimer() {
    if (timer) { clearInterval(timer); timer = null; }
  }
  function hide() {
    box.hidden = true;
    document.body.style.overflow = "";
    clearTimer();
  }
  function show() {
    box.hidden = false;
    document.body.style.overflow = "hidden";

    var manual = cfg.close_mode === "manual";
    if (closeBtn) closeBtn.hidden = !manual;

    if (manual) {
      if (countdownEl) countdownEl.hidden = true;
      return;
    }

    // 点击其他位置关闭：不显示关闭按钮，可选倒计时
    if (countdownEl) countdownEl.hidden = true;
    var seconds = parseInt(cfg.countdown, 10) || 0;
    if (seconds > 0 && countdownEl) {
      countdownEl.hidden = false;
      var remain = seconds;
      countdownEl.textContent = "将在 " + remain + " 秒后自动关闭";
      timer = setInterval(function () {
        remain -= 1;
        if (remain <= 0) { hide(); return; }
        countdownEl.textContent = "将在 " + remain + " 秒后自动关闭";
      }, 1000);
    }
  }

  // 触发场景
  var mode = cfg.mode || "daily_first";
  var should = false;
  var daily = false;

  if (mode === "every_open") {
    should = true;
  } else if (mode === "daily_first") {
    should = lastDate() !== today();
    daily = true;
  } else if (mode === "scheduled") {
    var now = new Date();
    var start = cfg.start ? new Date(cfg.start) : null;
    var end = cfg.end ? new Date(cfg.end) : null;
    var inRange = (!start || now >= start) && (!end || now <= end);
    if (inRange) {
      if (cfg.daily_once) {
        should = lastDate() !== today();
        daily = true;
      } else {
        should = true;
      }
    }
  }

  if (!should) return;

  setTimeout(show, 500);
  if (daily) mark();

  if (closeBtn) closeBtn.addEventListener("click", hide);

  // 只有「点击其他位置关闭」模式才允许点遮罩关闭
  box.addEventListener("click", function (e) {
    if (cfg.close_mode !== "manual" && e.target === box) hide();
  });

  // 手动强制模式下 Esc 也不关闭
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !box.hidden && cfg.close_mode !== "manual") hide();
  });

  // 点击图片或文章内容跳转时，先关闭弹窗
  var link = box.querySelector(".site-popup-link");
  if (link) link.addEventListener("click", hide);
})();
