/* ============================================================
   音乐播放器（圆盘 / 音乐卡片两种样式）
   支持：进度、音量、静音、上下曲、平台嵌入
   ============================================================ */
(function () {
  "use strict";

  var dataEl = document.getElementById("tracks-data");
  if (!dataEl) return;

  var tracks;
  try { tracks = JSON.parse(dataEl.textContent); } catch (e) { return; }
  if (!Array.isArray(tracks) || !tracks.length) return;

  var player = document.getElementById("player");
  var audio = document.getElementById("player-audio");
  if (!player || !audio) return;

  var el = {
    disc: document.getElementById("p-disc"),
    coverImg: document.getElementById("p-cover-img"),
    fallback: document.getElementById("p-cover-fallback"),
    title: document.getElementById("p-title"),
    artist: document.getElementById("p-artist"),
    prev: document.getElementById("p-prev"),
    play: document.getElementById("p-play"),
    next: document.getElementById("p-next"),
    iconPlay: document.getElementById("p-icon-play"),
    iconPause: document.getElementById("p-icon-pause"),
    cur: document.getElementById("p-cur"),
    dur: document.getElementById("p-dur"),
    seek: document.getElementById("p-seek"),
    volume: document.getElementById("p-volume"),
    mute: document.getElementById("p-mute"),
    embed: document.getElementById("p-embed"),
    iframe: document.getElementById("p-iframe"),
    embedName: document.getElementById("p-embed-name")
  };

  var PLATFORM = { custom: "直链", netease: "网易云", qq: "QQ音乐", soda: "汽水音乐" };
  var index = -1;
  var mode = "none";

  function fmt(sec) {
    if (!isFinite(sec) || sec < 0) sec = 0;
    var m = Math.floor(sec / 60);
    var s = Math.floor(sec % 60);
    return m + ":" + (s < 10 ? "0" + s : s);
  }

  function setCover(src) {
    if (src) {
      el.coverImg.src = src;
      el.coverImg.hidden = false;
      el.fallback.hidden = true;
    } else {
      el.coverImg.hidden = true;
      el.coverImg.removeAttribute("src");
      el.fallback.hidden = false;
    }
  }

  function setPlaying(playing) {
    if (el.iconPlay) el.iconPlay.style.display = playing ? "none" : "block";
    if (el.iconPause) el.iconPause.style.display = playing ? "block" : "none";
    el.play.setAttribute("aria-label", playing ? "暂停" : "播放");
    el.disc.classList.toggle("playing", !!playing);
  }

  function updateMeta(t) {
    el.title.textContent = t.title || "未命名曲目";
    el.artist.textContent = t.artist || PLATFORM[t.platform] || "";
    setCover(t.cover);
  }

  function resetProgress() {
    el.cur.textContent = "0:00";
    el.dur.textContent = "0:00";
    el.seek.value = 0;
  }

  function setVolume(value) {
    var v = Math.max(0, Math.min(100, Number(value)));
    audio.volume = v / 100;
    audio.muted = false;
    if (el.volume) el.volume.value = v;
    if (el.mute) el.mute.style.opacity = v === 0 ? ".4" : "1";
  }

  function closeEmbed() {
    el.embed.hidden = true;
    if (el.iframe) el.iframe.removeAttribute("src");
  }

  function openEmbed(url, name) {
    if (el.iframe) el.iframe.src = url;
    el.embedName.textContent = name;
    el.embed.hidden = false;
  }

  function playIndex(i, autoplay) {
    if (i < 0) i = tracks.length - 1;
    if (i >= tracks.length) i = 0;
    index = i;
    var t = tracks[i];

    updateMeta(t);
    setPlaying(false);
    resetProgress();
    closeEmbed();

    if (t.kind === "audio" && t.play_url) {
      mode = "audio";
      player.classList.remove("is-embed");
      audio.src = t.play_url;
      audio.load();
      if (autoplay !== false) {
        var pr = audio.play();
        if (pr && pr.catch) pr.catch(function () {});
      }
    } else if (t.kind === "embed" && t.embed_url) {
      mode = "embed";
      player.classList.add("is-embed");
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
      openEmbed(t.embed_url, (PLATFORM[t.platform] || "平台") + " · " + (t.title || ""));
    } else {
      mode = "none";
      player.classList.add("is-embed");
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
    }

    try { localStorage.setItem("blog_player_index", String(index)); } catch (e) {}
  }

  function next() { playIndex(index + 1); }
  function prev() { playIndex(index - 1); }

  function togglePlay() {
    if (mode === "embed") {
      el.embed.hidden = false;
      return;
    }
    if (mode === "none" || index < 0) {
      playIndex(index < 0 ? 0 : index);
      return;
    }
    if (audio.paused) {
      var pr = audio.play();
      if (pr && pr.catch) pr.catch(function () {});
    } else {
      audio.pause();
    }
  }

  if (el.play) el.play.addEventListener("click", togglePlay);
  if (el.disc) el.disc.addEventListener("click", togglePlay);
  if (el.next) el.next.addEventListener("click", next);
  if (el.prev) el.prev.addEventListener("click", prev);

  audio.addEventListener("play", function () {
    setPlaying(true);
    if (window.trackEvent) {
      var t = tracks[index];
      window.trackEvent("music_play", { label: t && t.title ? t.title : "" });
    }
  });
  audio.addEventListener("pause", function () { setPlaying(false); });
  audio.addEventListener("ended", next);

  audio.addEventListener("loadedmetadata", function () {
    el.dur.textContent = fmt(audio.duration);
  });
  audio.addEventListener("timeupdate", function () {
    el.cur.textContent = fmt(audio.currentTime);
    if (audio.duration) {
      el.seek.value = Math.round((audio.currentTime / audio.duration) * 1000);
    }
  });

  if (el.seek) {
    el.seek.addEventListener("input", function () {
      if (audio.duration && mode === "audio") {
        audio.currentTime = (el.seek.value / 1000) * audio.duration;
      }
    });
  }

  if (el.volume) {
    el.volume.addEventListener("input", function () { setVolume(el.volume.value); });
  }
  if (el.mute) {
    el.mute.addEventListener("click", function () {
      if (audio.muted || audio.volume === 0) {
        audio.muted = false;
        setVolume(el.volume ? el.volume.value : 80);
      } else {
        audio.muted = true;
        el.mute.style.opacity = ".4";
      }
    });
  }

  document.querySelectorAll("[data-close]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var panel = document.getElementById(btn.getAttribute("data-close"));
      if (panel) panel.hidden = true;
    });
  });

  document.addEventListener("keydown", function (e) {
    if (e.target && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    if (e.code === "Space") { e.preventDefault(); togglePlay(); }
  });

  // 初始化
  setVolume(player.dataset.volume || 80);

  var saved = 0;
  try {
    var s = parseInt(localStorage.getItem("blog_player_index"), 10);
    if (!isNaN(s) && s >= 0 && s < tracks.length) saved = s;
  } catch (e) {}

  (function init() {
    var t = tracks[saved];
    index = saved;
    updateMeta(t);
    setPlaying(false);
    if (t.kind === "audio" && t.play_url) {
      mode = "audio";
      player.classList.remove("is-embed");
      audio.src = t.play_url;
      audio.load();
    } else if (t.kind === "embed" && t.embed_url) {
      mode = "embed";
      player.classList.add("is-embed");
      if (el.iframe) el.iframe.src = t.embed_url;
      el.embedName.textContent = (PLATFORM[t.platform] || "平台") + " · " + (t.title || "");
    } else {
      mode = "none";
      player.classList.add("is-embed");
    }

    if (player.dataset.autoplay === "1" && t.kind === "audio") {
      var pr = audio.play();
      if (pr && pr.catch) pr.catch(function () {});
    }
  })();
})();
