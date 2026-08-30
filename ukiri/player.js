    (function () {
      var player = document.getElementById("mainPlayer");
      var source = document.getElementById("mainSource");
      var title = document.getElementById("playerTitle");
      var meta = document.getElementById("playerMeta");
      var dl = document.getElementById("playerDownload");
      var captions = document.getElementById("mainCaptions");
      if (!player || !source) return;
      document.querySelectorAll(".video-card[data-src]").forEach(function (card) {
        card.addEventListener("click", function () {
          var src = card.getAttribute("data-src");
          var poster = card.getAttribute("data-poster") || "";
          var cap = card.getAttribute("data-captions") || "";
          var t = card.getAttribute("data-title") || "Ukiri roast";
          var m = card.getAttribute("data-meta") || "";
          source.src = src;
          if (captions) {
            if (cap) {
              captions.src = cap;
              captions.default = true;
              captions.track && (captions.track.mode = "showing");
            } else {
              captions.removeAttribute("src");
            }
          }
          player.poster = poster;
          player.load();
          player.scrollIntoView({ behavior: "smooth", block: "center" });
          try { player.play(); } catch (e) {}
          if (title) title.textContent = t;
          if (meta) meta.textContent = " · " + m;
          if (dl) { dl.href = src; }
          document.querySelectorAll(".video-card").forEach(function (c) { c.classList.remove("is-active"); });
          card.classList.add("is-active");
        });
      });
    })();
