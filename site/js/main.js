/* ICE RIOT — site interactions. No dependencies. */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  /* ---------- nav background on scroll ---------- */
  var nav = $("#nav");
  function onScroll() { nav.classList.toggle("scrolled", window.scrollY > 40); }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ---------- reveal on scroll + stat count-up ---------- */
  function countUp(el) {
    var target = parseInt(el.getAttribute("data-count"), 10);
    if (!target || reduceMotion.matches) return;
    var start = performance.now();
    var dur = 900 + Math.min(target, 200) * 4;
    function tick(t) {
      var p = Math.min(1, (t - start) / dur);
      var e = 1 - Math.pow(1 - p, 3);
      el.textContent = String(Math.round(target * e));
      if (p < 1) requestAnimationFrame(tick);
    }
    el.textContent = "0";
    requestAnimationFrame(tick);
  }

  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        en.target.classList.add("in");
        $$("[data-count]", en.target).forEach(countUp);
        io.unobserve(en.target);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    $$(".reveal").forEach(function (el) { io.observe(el); });
  } else {
    $$(".reveal").forEach(function (el) { el.classList.add("in"); });
  }

  /* ---------- WebGPU detection ---------- */
  var chip = $("#gpu-chip");
  var chipText = $("#gpu-text");
  var gpuOk = null; // null = unknown/checking
  var touchOnly = window.matchMedia("(hover: none) and (pointer: coarse)").matches;

  function setGpu(ok, msg) {
    gpuOk = ok;
    chip.setAttribute("data-state", ok ? "ok" : "no");
    chipText.innerHTML = "";
    chipText.appendChild(document.createTextNode(msg));
    if (!ok) {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = "Options";
      b.addEventListener("click", openGpuDialog);
      chipText.appendChild(document.createTextNode(" "));
      chipText.appendChild(b);
    }
  }

  (function detect() {
    if (!navigator.gpu) {
      setGpu(false, "This browser has no WebGPU. Use desktop Chrome, Edge or Safari 26+, or get the Mac build.");
      return;
    }
    var timeout = new Promise(function (res) { setTimeout(function () { res("timeout"); }, 2500); });
    Promise.race([navigator.gpu.requestAdapter().catch(function () { return null; }), timeout]).then(function (adapter) {
      if (adapter === "timeout") { setGpu(true, "WebGPU detected. Ready to play."); return; }
      if (!adapter) { setGpu(false, "WebGPU is present but no GPU adapter is available. Try another browser or the Mac build."); return; }
      setGpu(true, touchOnly ? "WebGPU ready. Bring a keyboard or gamepad." : "WebGPU ready. Plug in a gamepad or use the keyboard.");
    });
  })();

  var gpuDialog = $("#gpu-dialog");
  function openGpuDialog() {
    if (typeof gpuDialog.showModal === "function") gpuDialog.showModal();
    else window.location.href = "play/";
  }
  $$(".js-play").forEach(function (a) {
    a.addEventListener("click", function (e) {
      if (gpuOk === false && !e.metaKey && !e.ctrlKey && !e.shiftKey) {
        e.preventDefault();
        openGpuDialog();
      }
    });
  });
  $$("dialog [data-close]").forEach(function (b) {
    b.addEventListener("click", function () { b.closest("dialog").close(); });
  });
  $$("dialog").forEach(function (d) {
    d.addEventListener("click", function (e) { if (e.target === d) d.close(); });
  });

  /* ---------- trailer: only show if the file exists ---------- */
  fetch("media/trailer.mp4", { method: "HEAD" }).then(function (r) {
    var type = r.headers.get("content-type") || "";
    if (!r.ok || type.indexOf("html") !== -1) return;
    var v = $("#trailer-video");
    v.src = "media/trailer.mp4";
    $("#trailer").hidden = false;
  }).catch(function () {});

  /* ---------- team card tilt ---------- */
  if (!reduceMotion.matches && window.matchMedia("(hover: hover)").matches) {
    $$(".team-card").forEach(function (card) {
      card.addEventListener("pointermove", function (e) {
        var r = card.getBoundingClientRect();
        var x = (e.clientX - r.left) / r.width;
        var y = (e.clientY - r.top) / r.height;
        card.style.setProperty("--ry", ((x - 0.5) * 16).toFixed(2) + "deg");
        card.style.setProperty("--rx", ((0.5 - y) * 14).toFixed(2) + "deg");
        card.style.setProperty("--mx", (x * 100).toFixed(1) + "%");
        card.style.setProperty("--my", (y * 100).toFixed(1) + "%");
      });
      card.addEventListener("pointerleave", function () {
        card.style.removeProperty("--rx");
        card.style.removeProperty("--ry");
      });
    });
  }
  // touch: tap toggles the color reveal
  $$(".team-card").forEach(function (card) {
    card.addEventListener("click", function () {
      if (!window.matchMedia("(hover: none)").matches) return;
      var on = card.classList.toggle("on");
      $$(".team-card.on").forEach(function (c) { if (c !== card && on) c.classList.remove("on"); });
    });
  });

  /* ---------- gallery lightbox ---------- */
  var shots = $$(".shot");
  var lb = $("#lightbox");
  var lbImg = $("#lightbox-img");
  var lbCap = $("#lightbox-cap");
  var lbIndex = 0;
  function showShot(i) {
    lbIndex = (i + shots.length) % shots.length;
    var s = shots[lbIndex];
    var img = $("img", s);
    lbImg.src = s.dataset.full || img.currentSrc || img.src;
    lbImg.alt = img.alt;
    lbCap.textContent = $(".cap", s).textContent + (img.dataset.fellBack ? " · Blender render" : "");
  }
  shots.forEach(function (s, i) {
    s.addEventListener("click", function () {
      showShot(i);
      if (typeof lb.showModal === "function") lb.showModal();
    });
  });
  $("#lb-prev").addEventListener("click", function () { showShot(lbIndex - 1); });
  $("#lb-next").addEventListener("click", function () { showShot(lbIndex + 1); });
  lb.addEventListener("keydown", function (e) {
    if (e.key === "ArrowLeft") { e.preventDefault(); showShot(lbIndex - 1); }
    if (e.key === "ArrowRight") { e.preventDefault(); showShot(lbIndex + 1); }
  });

  /* ---------- cheat codes (type them anywhere on the page) ---------- */
  var toast = $("#toast");
  var toastTimer;
  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove("show"); }, 2200);
  }
  var CODES = {
    BIGHEAD: { cls: "cheat-bighead", label: "Big heads" },
    TINY: { cls: "cheat-tiny", label: "Tiny players" },
    ALLSTAR: { cls: "cheat-allstar", label: "Super teams" },
    FRENZY: { cls: "cheat-frenzy", label: "Fight frenzy" }
  };
  var typed = "";
  document.addEventListener("keydown", function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey || e.key.length !== 1) return;
    var t = e.target;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
    typed = (typed + e.key.toUpperCase()).slice(-12);
    Object.keys(CODES).forEach(function (code) {
      if (typed.slice(-code.length) !== code) return;
      typed = "";
      var c = CODES[code];
      var body = document.body;
      var tile = $('.cheat[data-code="' + code + '"]');
      if (code === "FRENZY") {
        body.classList.remove(c.cls);
        void body.offsetWidth; // restart the shake
        body.classList.add(c.cls);
        if (fx) fx.burst(60);
        if (tile) tile.classList.add("lit");
        showToast("Cheat on: " + c.label + "!");
        return;
      }
      if (code === "BIGHEAD") body.classList.remove("cheat-tiny");
      if (code === "TINY") body.classList.remove("cheat-bighead");
      var on = body.classList.toggle(c.cls);
      $$(".cheat").forEach(function (el) {
        var k = CODES[el.dataset.code];
        el.classList.toggle("lit", body.classList.contains(k.cls));
      });
      if (fx && on) fx.burst(30);
      showToast((on ? "Cheat on: " : "Cheat off: ") + c.label);
    });
  });

  /* ---------- hero FX canvas: ice shavings, sparks, embers ---------- */
  var fx = null;
  var canvas = $("#fx");
  if (canvas && canvas.getContext && !reduceMotion.matches) {
    fx = (function () {
      var ctx = canvas.getContext("2d");
      var hero = canvas.parentElement;
      var W = 0, H = 0, dpr = 1;
      var parts = [];
      var running = false, visible = true, raf = 0, last = 0;
      var spawnAcc = 0;

      function resize() {
        dpr = Math.min(window.devicePixelRatio || 1, 1.5);
        W = hero.clientWidth;
        H = hero.clientHeight;
        canvas.width = Math.round(W * dpr);
        canvas.height = Math.round(H * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }

      function rand(a, b) { return a + Math.random() * (b - a); }

      // kind 0: ice shaving streak (turbo wind), 1: spark from behind logo, 2: drifting snow
      function spawn(kind, x, y) {
        var p = { kind: kind, life: 0 };
        if (kind === 0) {
          p.x = rand(-0.2 * W, W);
          p.y = rand(-40, H * 0.9);
          var sp = rand(900, 1700);
          p.vx = sp; p.vy = sp * 0.16;
          p.len = rand(40, 140);
          p.max = rand(0.5, 1.1);
          p.w = rand(0.6, 1.8);
          p.hue = Math.random() < 0.75 ? "200,235,255" : "120,200,255";
        } else if (kind === 1) {
          var a = rand(0, Math.PI * 2);
          var s = rand(180, 620);
          p.x = x == null ? W / 2 + rand(-W * 0.22, W * 0.22) : x;
          p.y = y == null ? H * 0.42 + rand(-H * 0.08, H * 0.08) : y;
          p.vx = Math.cos(a) * s; p.vy = Math.sin(a) * s - 160;
          p.max = rand(0.5, 1.2);
          p.w = rand(1, 2.4);
          p.hot = Math.random();
        } else {
          p.x = rand(0, W); p.y = rand(-20, H);
          p.vx = rand(10, 40); p.vy = rand(14, 46);
          p.max = rand(4, 9);
          p.r = rand(0.6, 2.2);
          p.ph = rand(0, 6.28);
        }
        parts.push(p);
      }

      function burst(n, x, y) {
        for (var i = 0; i < n; i++) spawn(1, x, y);
        if (!running) start();
      }

      function step(t) {
        raf = requestAnimationFrame(step);
        var dt = Math.min(0.05, (t - last) / 1000 || 0.016);
        last = t;
        var area = (W * H) / (1440 * 900);
        spawnAcc += dt;
        // steady emission
        while (spawnAcc > 0.02) {
          spawnAcc -= 0.02;
          if (Math.random() < 0.55 * area + 0.15) spawn(0);
          if (Math.random() < 0.12) spawn(1);
          if (parts.length < 260 && Math.random() < 0.35 * area) spawn(2);
        }
        if (Math.random() < dt * 0.35) burst(Math.round(rand(14, 26)));

        ctx.clearRect(0, 0, W, H);
        ctx.globalCompositeOperation = "lighter";
        for (var i = parts.length - 1; i >= 0; i--) {
          var p = parts[i];
          p.life += dt;
          var k = p.life / p.max;
          if (k >= 1 || p.x > W + 200 || p.y > H + 60) { parts.splice(i, 1); continue; }
          if (p.kind === 0) {
            p.x += p.vx * dt; p.y += p.vy * dt;
            var al = Math.sin(k * Math.PI) * 0.55;
            var g = ctx.createLinearGradient(p.x - p.len, p.y - p.len * 0.16, p.x, p.y);
            g.addColorStop(0, "rgba(" + p.hue + ",0)");
            g.addColorStop(1, "rgba(" + p.hue + "," + al.toFixed(3) + ")");
            ctx.strokeStyle = g;
            ctx.lineWidth = p.w;
            ctx.beginPath();
            ctx.moveTo(p.x - p.len, p.y - p.len * 0.16);
            ctx.lineTo(p.x, p.y);
            ctx.stroke();
          } else if (p.kind === 1) {
            p.vy += 520 * dt;
            p.vx *= 1 - 1.2 * dt;
            var px = p.x, py = p.y;
            p.x += p.vx * dt; p.y += p.vy * dt;
            var fade = 1 - k;
            var col = p.hot > 0.5 ? "255," + Math.round(200 - 120 * k) + ",60" : "255," + Math.round(150 - 90 * k) + ",30";
            ctx.strokeStyle = "rgba(" + col + "," + fade.toFixed(3) + ")";
            ctx.lineWidth = p.w * fade + 0.3;
            ctx.beginPath();
            ctx.moveTo(px - p.vx * 0.02, py - p.vy * 0.02);
            ctx.lineTo(p.x, p.y);
            ctx.stroke();
          } else {
            p.ph += dt * 1.6;
            p.x += (p.vx + Math.sin(p.ph) * 18) * dt; p.y += p.vy * dt;
            var a2 = Math.sin(k * Math.PI) * 0.7;
            ctx.fillStyle = "rgba(220,240,255," + a2.toFixed(3) + ")";
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, 6.283);
            ctx.fill();
          }
        }
        ctx.globalCompositeOperation = "source-over";
      }

      function start() {
        if (running || !visible || document.hidden) return;
        running = true;
        last = performance.now();
        raf = requestAnimationFrame(step);
      }
      function stop() { running = false; cancelAnimationFrame(raf); }

      resize();
      window.addEventListener("resize", resize);
      if ("IntersectionObserver" in window) {
        new IntersectionObserver(function (en) {
          visible = en[0].isIntersecting;
          if (visible) start(); else stop();
        }).observe(hero);
      }
      document.addEventListener("visibilitychange", function () { if (document.hidden) stop(); else start(); });
      // logo slam burst
      setTimeout(function () { burst(70); }, 520);
      start();
      return { burst: burst };
    })();
  }
  reduceMotion.addEventListener && reduceMotion.addEventListener("change", function (e) {
    if (e.matches && canvas) canvas.style.display = "none";
  });
})();
