/* ============================================================
   FUTURE FANTASY ─未来の地図─  ティザー

   演出の順序
     1. 黒画面に 60TH が浮かぶ
     2. 背景が現れる（60TH は左上に置かれたまま）
     3. FUTURE FANTASY のエンブレム
     4. 文字を一行ずつ
   その後は、雲・光の粒・夕日・ロゴの照り返しだけが静かに動き続ける。
   ============================================================ */
(function () {
  'use strict';

  var stage = document.getElementById('stage');
  var motes = document.getElementById('motes');
  if (!stage) { return; }

  var reduceMotion = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* 各段の開始時刻(at)と長さ(for)。単位は秒 */
  var STEPS = [
    { step: 'crest',  at: 0.40, for: 1.40 },   // 1. 60TH
    { step: 'scene',  at: 1.55, for: 1.70 },   // 2. 背景
    { step: 'logo',   at: 3.00, for: 1.80 },   // 3. エンブレム
    { step: 'lead1',  at: 4.60, for: 0.95 },   // 4. 一行ずつ
    { step: 'lead2',  at: 5.00, for: 0.95 },
    { step: 'rule1',  at: 5.40, for: 0.80 },
    { step: 'date',   at: 5.65, for: 0.95 },
    { step: 'rule2',  at: 6.20, for: 0.80 },
    { step: 'coming', at: 6.45, for: 0.95 },
    { step: 'chev',   at: 7.15, for: 0.85 }
  ];

  var MOTES_AT = 3.2;
  var last = STEPS[STEPS.length - 1];
  var SETTLE_AT = last.at + last.for + 0.2;

  // ---------------------------------------------------------
  // 画面高さ（iOS のアドレスバー分を含む実寸）を CSS に渡す
  // ---------------------------------------------------------
  function syncViewport() {
    document.documentElement.style.setProperty('--app-h', window.innerHeight + 'px');
  }
  syncViewport();
  window.addEventListener('resize', syncViewport, { passive: true });
  window.addEventListener('orientationchange', function () {
    setTimeout(syncViewport, 240);
  }, { passive: true });

  // ---------------------------------------------------------
  // 段取りを CSS 変数として各要素に書き込む
  // ---------------------------------------------------------
  function schedule() {
    STEPS.forEach(function (s) {
      var el = s.step === 'scene'
        ? document.querySelector('.scene')
        : document.querySelector('[data-step="' + s.step + '"]');
      if (!el) { return; }
      el.style.setProperty('--at', s.at + 's');
      el.style.setProperty('--dur', s.for + 's');
      if (s.step === 'logo') {
        // 光の差し込みは、ロゴが着地する少し前から
        el.querySelector('.logo__flash')
          .style.setProperty('--flash-at', (s.at + 0.25) + 's');
      }
    });
  }

  // ---------------------------------------------------------
  // 光の粒。数秒に一粒ずつ、ゆっくり漂って消える
  // ---------------------------------------------------------
  var MAX_MOTES = 11;
  var live = 0;
  var timer = null;

  function spawn() {
    if (live >= MAX_MOTES || document.hidden) { return; }
    var rect = stage.getBoundingClientRect();
    if (!rect.width) { return; }

    var el = document.createElement('span');
    el.className = 'mote';

    var big = Math.random() < 0.22;              // ときどき大きめの粒
    var size = (big ? 0.9 : 0.34) + Math.random() * (big ? 0.5 : 0.4);
    var life = 8 + Math.random() * 8;

    el.style.width = size.toFixed(2) + '%';
    el.style.left = (6 + Math.random() * 88).toFixed(2) + '%';
    el.style.top = (26 + Math.random() * 62).toFixed(2) + '%';
    el.style.setProperty('--peak', (big ? 0.55 : 0.3) + Math.random() * 0.35);
    el.style.setProperty('--dx', ((Math.random() - 0.5) * rect.width * 0.1).toFixed(1) + 'px');
    el.style.setProperty('--dy', (-(0.04 + Math.random() * 0.07) * rect.height).toFixed(1) + 'px');
    el.style.animationDuration = life.toFixed(2) + 's';

    el.addEventListener('animationend', function () { el.remove(); live--; });
    motes.appendChild(el);
    live++;
  }

  function startMotes() {
    if (reduceMotion) { return; }
    spawn();
    (function loop() {
      timer = setTimeout(function () { spawn(); loop(); }, 1400 + Math.random() * 2200);
    }());
  }

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
      clearTimeout(timer);
      timer = null;
    } else if (!timer && !reduceMotion && document.body.classList.contains('is-settled')) {
      startMotes();
    }
  });

  // ---------------------------------------------------------
  // 進行
  // ---------------------------------------------------------
  function run() {
    if (reduceMotion) {
      document.body.classList.add('is-settled');
      return;
    }
    schedule();

    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        document.body.classList.add('is-playing');
        window.__heroStart = performance.now();     // 表示確認用

        setTimeout(startMotes, MOTES_AT * 1000);
        setTimeout(function () {
          document.body.classList.add('is-settled');
        }, SETTLE_AT * 1000);
      });
    });
  }

  // 絵がそろってから始める（途中から見えてしまわないように）
  var started = false;
  function begin() {
    if (started) { return; }
    started = true;
    run();
  }

  (function preload() {
    var names = ['scene', 'crest', 'logo', 'lead1', 'lead2', 'date', 'coming'];
    var left = names.length;
    names.forEach(function (n) {
      var img = new Image();
      img.onload = img.onerror = function () { if (--left === 0) { begin(); } };
      img.src = 'assets/img/hero/' + n + '.webp';
    });
  }());

  setTimeout(begin, 4000);   // 読み込みが極端に遅い場合の保険

  // ---------------------------------------------------------
  // PWA
  // ---------------------------------------------------------
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('sw.js').catch(function () { /* 表示には影響しない */ });
    });
  }
}());
