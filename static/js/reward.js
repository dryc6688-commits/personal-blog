/* 文章打赏弹窗 */
(function () {
  "use strict";

  var open = document.getElementById("reward-open");
  var modal = document.getElementById("reward-modal");
  if (!open || !modal) return;
  var close = document.getElementById("reward-close");

  function show() {
    modal.hidden = false;
    document.body.style.overflow = "hidden";
  }
  function hide() {
    modal.hidden = true;
    document.body.style.overflow = "";
  }

  open.addEventListener("click", show);
  if (close) close.addEventListener("click", hide);
  modal.addEventListener("click", function (e) { if (e.target === modal) hide(); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !modal.hidden) hide();
  });
})();
