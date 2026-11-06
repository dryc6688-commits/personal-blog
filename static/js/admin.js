/* ============================================================
   后台交互：文件上传、删除确认
   ============================================================ */
(function () {
  "use strict";

  function csrfToken() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.content : "";
  }

  // 删除确认
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.getAttribute("data-confirm"))) {
        e.preventDefault();
      }
    });
  });

  // 上传按钮
  document.querySelectorAll(".js-upload").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var targetSel = btn.getAttribute("data-target");
      var target = targetSel ? document.querySelector(targetSel) : null;
      if (!target) return;

      var accept = btn.getAttribute("data-accept") || "";
      var multi = btn.getAttribute("data-multi") === "1";

      var input = document.createElement("input");
      input.type = "file";
      if (accept) input.accept = accept;
      if (multi) input.multiple = true;
      input.style.display = "none";
      document.body.appendChild(input);

      input.addEventListener("change", function () {
        var files = Array.from(input.files || []);
        if (!files.length) { input.remove(); return; }

        var original = btn.textContent;
        btn.disabled = true;
        btn.textContent = "上传中…";

        var jobs = files.map(function (file) {
          var fd = new FormData();
          fd.append("file", file);
          return fetch("/admin/upload", { method: "POST", headers: { "X-CSRF-Token": csrfToken() }, body: fd })
            .then(function (r) { return r.json(); });
        });

        Promise.all(jobs).then(function (results) {
          var urls = [];
          var errors = [];
          results.forEach(function (res) {
            if (res && res.ok) urls.push(res.url);
            else errors.push((res && res.error) || "上传失败");
          });

          if (urls.length) {
            if (multi) {
              var existing = target.value.trim();
              target.value = (existing ? existing + "\n" : "") + urls.join("\n");
            } else {
              target.value = urls[0];
            }
            target.dispatchEvent(new Event("input", { bubbles: true }));
            target.dispatchEvent(new Event("change", { bubbles: true }));
          }
          if (errors.length) alert(errors.join("\n"));
        }).catch(function (err) {
          alert("上传出错：" + err.message);
        }).finally(function () {
          btn.disabled = false;
          btn.textContent = original;
          input.remove();
        });
      });

      input.click();
    });
  });

  // 复制文章链接
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      var path = btn.getAttribute("data-copy");
      var url = location.origin + path;
      var original = btn.textContent;
      function done() {
        btn.textContent = "已复制";
        setTimeout(function () { btn.textContent = original; }, 1500);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(done, function () {
          window.prompt("复制链接", url);
        });
      } else {
        window.prompt("复制链接", url);
      }
    });
  });
})();
