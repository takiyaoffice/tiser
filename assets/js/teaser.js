/* ============================================================
   仙台への冒険 ─ ティザーTOP画面
   ------------------------------------------------------------
   ・元のポスター画像（853 x 1844）は加工しない。
   ・座標はすべて元画像のピクセル値で書き、% へ変換して重ねる。
   ・動きは「よく見ると気付く」程度に抑える。
   ============================================================ */
(function () {
  'use strict';

  var POSTER_W = 853;
  var POSTER_H = 1844;

  var stage    = document.getElementById('stage');
  var patches  = document.getElementById('patches');
  var plateBox = document.getElementById('plates');
  var reveal   = document.getElementById('reveal');
  var motes    = document.getElementById('motes');

  if (!stage) { return; }

  var reduceMotion = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // 当て板は WebP（透過あり）のみ。使えない環境では文字を隠さず、背景だけを出す。
  var canWebp = document.createElement('canvas')
    .toDataURL('image/webp').indexOf('data:image/webp') === 0;

  /* ----------------------------------------------------------
     元画像のどこを動かすか
     box    : 動かす範囲（元画像のピクセル座標 x1,y1,x2,y2）
     pivot  : 変形の支点（同じくピクセル座標。尻尾なら付け根）
     plateau: マスクの中心側を完全不透明に保つ割合
     ---------------------------------------------------------- */
  var PATCHES = [
    {
      name: 'tail',                       // 茶々丸の尻尾
      box: [425, 1414, 530, 1504],
      pivot: [453, 1454],                 // 尻尾の付け根
      plateau: 70
    },
    {
      name: 'ears',                       // 茶々丸の耳
      box: [385, 1285, 475, 1385],
      pivot: [428, 1370],                 // 首のあたり
      plateau: 72
    },
    {
      name: 'grass',                      // 猫のとなりの草花
      box: [272, 1388, 408, 1500],
      pivotRatio: [0.5, 1.18],            // 根元よりさらに下を支点にする
      plateau: 62
    },
    {
      name: 'grass',                      // 崖ぎわの下草（弱い風、位相をずらす）
      box: [120, 1415, 232, 1497],
      pivotRatio: [0.5, 1.20],
      plateau: 58,
      delay: '-4.3s',
      scale: 0.65
    }
  ];

  /* ----------------------------------------------------------
     初回表示で順番に現れる文字

     box は当て板の画像そのものの範囲（元画像のピクセル座標）。
     tools/make_assets.py が出力した値をそのまま書いている。
     at  : 当て板が外れはじめる時刻(秒) / for: かかる時間(秒)
     ---------------------------------------------------------- */
  var PLATES = [
    { name: 'adv',    box: [136,  140, 724,  280],  at: 1.15, for: 0.85 }, // THE ADVENTURE
    { name: 'jp',     box: [  0,  234, 844,  496],  at: 1.65, for: 1.00 }, // 仙台への冒険
    { name: 'lead',   box: [ 64,  464, 790,  606],  at: 2.45, for: 0.80 }, // 60年の軌跡、…
    { name: 'date',   box: [176,  582, 678,  714],  at: 2.95, for: 0.80 }, // 2027.1.22 — 1.24
    { name: 'coming', box: [130,  688, 736,  822],  at: 3.45, for: 0.80 }, // A new adventure is coming…
    { name: 'map',    box: [196,  706, 666, 1126],  at: 3.95, for: 1.30 }, // 地図アイコン
    { name: 'tag',    box: [ 84, 1578, 766, 1716],  at: 4.75, for: 1.00 }  // まもなく、冒険がはじまる。
  ];

  var CURTAIN = { at: 0.15, for: 1.35 };   // 背景画像そのもの
  var ALIVE_AT = 4.6;                      // 地図と茶々丸が動きはじめる時刻
  var MOTES_AT = 3.0;                      // 光の粒が漂いはじめる時刻
  var SETTLE_AT = PLATES[PLATES.length - 1].at + PLATES[PLATES.length - 1].for + 0.35;

  // ---------------------------------------------------------
  // ちいさなヘルパー
  // ---------------------------------------------------------
  function pct(value) { return (Math.round(value * 10000) / 100) + '%'; }

  function place(el, box) {
    var w = (box[2] - box[0]) / POSTER_W;
    var h = (box[3] - box[1]) / POSTER_H;
    var l = box[0] / POSTER_W;
    var t = box[1] / POSTER_H;

    el.style.left   = pct(l);
    el.style.top    = pct(t);
    el.style.width  = pct(w);
    el.style.height = pct(h);

    return { l: l, t: t, w: w, h: h };
  }

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
  // 4 & 5. 茶々丸と草花
  //   元画像の同じ場所を同じ大きさで重ねるので、静止時は完全に一致する。
  //   わずかに回転／傾けたときだけ、そこにある物が動いて見える。
  // ---------------------------------------------------------
  function buildPatches() {
    PATCHES.forEach(function (spec) {
      var el = document.createElement('div');
      el.className = 'patch patch--' + spec.name;

      var g = place(el, spec.box);

      // 要素の中に、ステージ全体と同じ縮尺でポスターを敷く
      el.style.backgroundSize = pct(1 / g.w) + ' ' + pct(1 / g.h);
      el.style.backgroundPosition =
        pct(g.l / (1 - g.w)) + ' ' + pct(g.t / (1 - g.h));

      el.style.setProperty('--plateau', spec.plateau + '%');

      if (spec.pivot) {
        el.style.transformOrigin =
          pct((spec.pivot[0] - spec.box[0]) / (spec.box[2] - spec.box[0])) + ' ' +
          pct((spec.pivot[1] - spec.box[1]) / (spec.box[3] - spec.box[1]));
      } else if (spec.pivotRatio) {
        el.style.transformOrigin =
          pct(spec.pivotRatio[0]) + ' ' + pct(spec.pivotRatio[1]);
      }

      if (spec.delay) { el.style.animationDelay = spec.delay; }
      if (spec.scale) { el.style.setProperty('--amp', spec.scale); }

      patches.appendChild(el);
    });
  }

  // ---------------------------------------------------------
  // 初回表示：幕を順番に上げる
  // ---------------------------------------------------------
  function buildReveal() {
    // 暗幕は HTML にあらかじめ置いてある（読み込み直後のちらつき防止）
    var curtain = reveal.querySelector('.curtain');
    curtain.style.animationDelay = CURTAIN.at + 's';
    curtain.style.animationDuration = CURTAIN.for + 's';

    if (!canWebp) { return; }

    PLATES.forEach(function (spec) {
      var el = document.createElement('div');
      el.className = 'plate plate--' + spec.name;
      place(el, spec.box);
      el.style.backgroundImage = 'url("assets/img/plate/' + spec.name + '.webp")';
      el.style.animationDelay = spec.at + 's';
      el.style.animationDuration = spec.for + 's';
      plateBox.appendChild(el);
    });
  }

  // ---------------------------------------------------------
  // 2. 光の粒
  //   数秒に一度、少しだけ。小さく、上品に。
  // ---------------------------------------------------------
  var MAX_MOTES = 9;
  var liveMotes = 0;
  var moteTimer = null;

  function spawnMote() {
    if (liveMotes >= MAX_MOTES || document.hidden) { return; }

    var rect = stage.getBoundingClientRect();
    if (!rect.width) { return; }

    var el = document.createElement('span');
    el.className = 'mote';

    var size = 0.32 + Math.random() * 0.42;            // ステージ幅に対する %
    var life = 9 + Math.random() * 7;                   // 9〜16秒かけて漂う

    el.style.width = size.toFixed(2) + '%';
    el.style.left = (4 + Math.random() * 92).toFixed(2) + '%';
    el.style.top = (22 + Math.random() * 66).toFixed(2) + '%';
    el.style.setProperty('--peak', (0.28 + Math.random() * 0.34).toFixed(2));
    el.style.setProperty('--dx', ((Math.random() - 0.5) * rect.width * 0.09).toFixed(1) + 'px');
    el.style.setProperty('--dy', (-(0.03 + Math.random() * 0.05) * rect.height).toFixed(1) + 'px');
    el.style.animationDuration = life.toFixed(2) + 's';

    el.addEventListener('animationend', function () {
      el.remove();
      liveMotes--;
    });

    motes.appendChild(el);
    liveMotes++;
  }

  function startMotes() {
    if (reduceMotion) { return; }

    // 最初の数粒は間隔を空けて、静かに漂いはじめる
    spawnMote();
    (function loop() {
      moteTimer = setTimeout(function () {
        spawnMote();
        loop();
      }, 2200 + Math.random() * 2600);
    }());
  }

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
      clearTimeout(moteTimer);
      moteTimer = null;
    } else if (!moteTimer && !reduceMotion && document.body.classList.contains('is-settled')) {
      startMotes();
    }
  });

  // ---------------------------------------------------------
  // 進行
  // ---------------------------------------------------------
  function run() {
    buildPatches();

    if (reduceMotion) {
      document.body.classList.add('is-settled');
      return;
    }

    buildReveal();

    // 画像の準備が整ってから幕を上げる（途中から始まって見えないように）
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        document.body.classList.add('is-revealing');
        window.__teaserStart = performance.now();   // 表示確認用

        setTimeout(function () { document.body.classList.add('is-alive'); }, ALIVE_AT * 1000);
        setTimeout(startMotes, MOTES_AT * 1000);
        setTimeout(function () { document.body.classList.add('is-settled'); }, SETTLE_AT * 1000);
      });
    });
  }

  // ポスターと当て板がそろってから始める（途中から見えてしまわないように）
  var started = false;

  function begin() {
    if (started) { return; }
    started = true;
    run();
  }

  (function preload() {
    var sources = [canWebp ? 'assets/img/teaser.webp' : 'assets/img/teaser.png'];
    if (canWebp && !reduceMotion) {
      PLATES.forEach(function (spec) {
        sources.push('assets/img/plate/' + spec.name + '.webp');
      });
    }

    var left = sources.length;
    sources.forEach(function (src) {
      var img = new Image();
      img.onload = img.onerror = function () {
        if (--left === 0) { begin(); }
      };
      img.src = src;
    });
  }());

  // 念のため、読み込みが極端に遅い場合も 3.5 秒で始める
  setTimeout(begin, 3500);

  // ---------------------------------------------------------
  // PWA
  // ---------------------------------------------------------
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('sw.js').catch(function () { /* 失敗しても表示に影響しない */ });
    });
  }
}());
