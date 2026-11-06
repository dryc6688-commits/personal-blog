/* 文章点赞：所有人可见，可点赞 / 取消 */
(function () {
  "use strict";

  function csrfToken() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.content : "";
  }

  var btn = document.getElementById("like-btn");
  if (!btn) return;
  var pid = btn.getAttribute("data-post-id");
  var countEl = document.getElementById("like-count");
  var labelEl = btn.querySelector(".like-label");

  btn.addEventListener("click", function () {
    if (btn.disabled) return;
    btn.disabled = true;
    if (window.trackEvent) {
      window.trackEvent("like_click", { post_id: parseInt(pid, 10) || null });
    }
    fetch("/api/like/" + pid, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() } })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (res && res.ok) {
          btn.classList.toggle("liked", !!res.liked);
          if (countEl) countEl.textContent = res.count;
          if (labelEl) labelEl.textContent = res.liked ? "已赞" : "点赞";
        } else if (res && res.error) {
          alert(res.error);
        }
      })
      .catch(function () {})
      .finally(function () { btn.disabled = false; });
  });
})();
