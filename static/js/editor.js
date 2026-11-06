/* ============================================================
   后台富文本编辑器
   支持：字号、加粗、斜体、下划线、颜色、标题、引用、
        列表、代码块、链接、多图上传、多视频插入、清除格式
   ============================================================ */
(function () {
  "use strict";

  var editor = document.getElementById("rich-editor");
  if (!editor) return;

  var form = document.getElementById("post-form");
  var hidden = document.getElementById("content");
  var lastRange = null;

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function escapeAttr(s) {
    return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function sync() {
    if (hidden) hidden.value = editor.innerHTML;
  }

  function inEditor(node) {
    return node && (node === editor || editor.contains(node));
  }
  function saveSelection() {
    var sel = window.getSelection();
    if (sel && sel.rangeCount && inEditor(sel.anchorNode)) {
      lastRange = sel.getRangeAt(0).cloneRange();
    }
  }
  function restoreSelection() {
    editor.focus();
    var sel = window.getSelection();
    if (lastRange) {
      sel.removeAllRanges();
      sel.addRange(lastRange);
    } else {
      var r = document.createRange();
      r.selectNodeContents(editor);
      r.collapse(false);
      sel.removeAllRanges();
      sel.addRange(r);
    }
  }
  function exec(cmd, val) {
    editor.focus();
    document.execCommand(cmd, false, val);
    sync();
  }
  function insertHtml(html) {
    restoreSelection();
    document.execCommand("insertHTML", false, html);
    sync();
    saveSelection();
  }
  function uploadFile(file) {
    var fd = new FormData();
    fd.append("file", file);
    return fetch("/admin/upload", { method: "POST", body: fd })
      .then(function (r) { return r.json(); })
      .catch(function (e) { return { ok: false, error: e.message }; });
  }

  document.addEventListener("selectionchange", saveSelection);
  editor.addEventListener("keyup", saveSelection);
  editor.addEventListener("mouseup", saveSelection);
  editor.addEventListener("input", sync);
  if (form) form.addEventListener("submit", sync);
  sync();

  // 通用命令按钮
  document.querySelectorAll("#editor-toolbar [data-cmd]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      exec(btn.getAttribute("data-cmd"));
    });
  });

  // 段落格式
  document.querySelectorAll("#editor-toolbar [data-block]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      exec("formatBlock", btn.getAttribute("data-block"));
    });
  });

  // 字号
  var sizeSel = document.getElementById("tb-size");
  if (sizeSel) {
    sizeSel.addEventListener("change", function () {
      if (sizeSel.value) {
        exec("fontSize", sizeSel.value);
        sizeSel.value = "";
      }
    });
  }

  // 颜色
  var colorInput = document.getElementById("tb-color");
  if (colorInput) {
    colorInput.addEventListener("input", function () {
      exec("foreColor", colorInput.value);
    });
  }

  // 代码块
  var codeBtn = document.getElementById("tb-code");
  if (codeBtn) {
    codeBtn.addEventListener("click", function () {
      editor.focus();
      var sel = window.getSelection();
      var text = (sel && !sel.isCollapsed) ? sel.toString() : "在这里输入代码";
      insertHtml("<pre><code>" + escapeHtml(text) + "</code></pre><p><br></p>");
    });
  }

  // 链接
  var linkBtn = document.getElementById("tb-link");
  if (linkBtn) {
    linkBtn.addEventListener("click", function () {
      editor.focus();
      var sel = window.getSelection();
      if (sel && !sel.isCollapsed) {
        var url = prompt("请输入链接地址（https://...）");
        if (url) exec("createLink", url);
      } else {
        var text = prompt("链接文字", "链接文字");
        if (text === null) return;
        var href = prompt("链接地址（https://...）");
        if (!href) return;
        insertHtml('<a href="' + escapeAttr(href) + '">' + escapeHtml(text) + "</a>");
      }
    });
  }

  // ---------------- 多图插入 ----------------
  var imgBtn = document.getElementById("tb-image");
  if (imgBtn) {
    var imgInput = document.createElement("input");
    imgInput.type = "file";
    imgInput.accept = "image/*";
    imgInput.multiple = true;
    imgInput.style.display = "none";
    document.body.appendChild(imgInput);

    imgBtn.addEventListener("click", function () {
      saveSelection();
      imgInput.value = "";
      imgInput.click();
    });

    imgInput.addEventListener("change", function () {
      var files = Array.prototype.slice.call(imgInput.files || []);
      if (!files.length) return;
      var original = imgBtn.textContent;
      imgBtn.disabled = true;
      imgBtn.textContent = "上传中…";
      Promise.all(files.map(uploadFile)).then(function (results) {
        var html = results.filter(function (r) { return r && r.ok; })
          .map(function (r) {
            return '<p><img src="' + escapeAttr(r.url) + '" alt=""></p>';
          }).join("");
        var failed = results.filter(function (r) { return !r || !r.ok; });
        if (html) insertHtml(html + "<p><br></p>");
        if (failed.length) alert("部分图片上传失败");
      }).finally(function () {
        imgBtn.disabled = false;
        imgBtn.textContent = original;
      });
    });
  }

  // ---------------- 多视频插入 ----------------
  var videoBtn = document.getElementById("tb-video");
  var videoModal = document.getElementById("video-modal");
  var videoUrlInput = document.getElementById("video-url-input");

  function toEmbedUrl(url) {
    var m = url.match(/bilibili\.com\/video\/(BV[\w]+)/i);
    if (m) {
      return "https://player.bilibili.com/player.html?bvid=" + m[1] + "&page=1&high_quality=1&danmaku=0";
    }
    m = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]+)/i);
    if (m) {
      return "https://www.youtube.com/embed/" + m[1];
    }
    return url;
  }
  function isDirectVideo(url) {
    return /\.(mp4|webm|ogg|ogv|mov|m4v)(\?|#|$)/i.test(url);
  }
  function buildVideoHtml(url) {
    if (isDirectVideo(url)) {
      return '<p><video class="post-video" controls playsinline src="' + escapeAttr(url) + '"></video></p>';
    }
    return '<div class="post-video-embed"><iframe src="' + escapeAttr(toEmbedUrl(url)) +
      '" frameborder="0" allowfullscreen allow="autoplay; encrypted-media; picture-in-picture"></iframe></div><p><br></p>';
  }

  if (videoBtn && videoModal) {
    var videoInput = document.createElement("input");
    videoInput.type = "file";
    videoInput.accept = "video/*";
    videoInput.style.display = "none";
    document.body.appendChild(videoInput);

    function closeVideoModal() { videoModal.hidden = true; }

    videoBtn.addEventListener("click", function () {
      saveSelection();
      videoModal.hidden = false;
      if (videoUrlInput) { videoUrlInput.value = ""; setTimeout(function () { videoUrlInput.focus(); }, 30); }
    });
    var closeBtn = document.getElementById("video-modal-close");
    if (closeBtn) closeBtn.addEventListener("click", closeVideoModal);
    videoModal.addEventListener("click", function (e) {
      if (e.target === videoModal) closeVideoModal();
    });

    var insertBtn = document.getElementById("video-insert-btn");
    if (insertBtn) {
      insertBtn.addEventListener("click", function () {
        var url = (videoUrlInput && videoUrlInput.value || "").trim();
        if (!url) { alert("请输入视频地址，或上传本地视频"); return; }
        insertHtml(buildVideoHtml(url));
        closeVideoModal();
      });
    }

    var uploadBtn = document.getElementById("video-upload-btn");
    if (uploadBtn) {
      uploadBtn.addEventListener("click", function () {
        videoInput.value = "";
        videoInput.click();
      });
    }
    videoInput.addEventListener("change", function () {
      var f = videoInput.files && videoInput.files[0];
      if (!f) return;
      var original = uploadBtn.textContent;
      uploadBtn.disabled = true;
      uploadBtn.textContent = "上传中…";
      uploadFile(f).then(function (res) {
        if (res && res.ok) {
          insertHtml('<p><video class="post-video" controls playsinline src="' +
            escapeAttr(res.url) + '"></video></p><p><br></p>');
          closeVideoModal();
        } else {
          alert((res && res.error) || "上传失败");
        }
      }).finally(function () {
        uploadBtn.disabled = false;
        uploadBtn.textContent = original;
      });
    });
  }
})();
