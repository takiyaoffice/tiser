/* ============================================================
   FUTURE FANTASY ─未来の地図─  ティザー

   演出の順序
     1. 黒画面の中央に 60TH が浮かび、霧のようにほどけて消える
     2. 背景が現れる（60TH は左上に移り、そのまま居続ける）
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
    // 1. 黒画面の中央に 60TH。浮かぶ→留まる→霧のようにほどける
    { step: 'herald', at: 0.50, for: 4.60 },
    // 2. 背景（左上の 60TH はここから居続ける）
    { step: 'scene',  at: 3.90, for: 2.30 },
    { step: 'crest',  at: 5.10, for: 1.80 },
    // 3. エンブレム
    { step: 'logo',   at: 6.30, for: 2.50 },
    // 4. 文字を一行ずつ。一行ごとに間を取り、ゆっくり浮かび上がらせる
    { step: 'lead1',  at: 8.60, for: 1.90 },
    { step: 'lead2',  at: 9.80, for: 1.90 },
    { step: 'rule1',  at: 10.90, for: 1.40 },
    { step: 'date',   at: 11.40, for: 1.90 },
    { step: 'rule2',  at: 12.70, for: 1.40 },
    { step: 'coming', at: 13.20, for: 2.00 }
  ];

  var MOTES_AT = 5.2;
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
    var byName = { scene: '.scene', herald: '.herald' };

    // 音のボタンは背景と一緒に出す
    var btn = document.getElementById('sound');
    if (btn) { btn.style.setProperty('--at', AUDIO_AT + 's'); }

    STEPS.forEach(function (s) {
      var el = byName[s.step]
        ? document.querySelector(byName[s.step])
        : document.querySelector('[data-step="' + s.step + '"]');
      if (!el) { return; }
      el.style.setProperty('--at', s.at + 's');
      el.style.setProperty('--dur', s.for + 's');
      if (s.step === 'logo') {
        // 光の差し込みは、ロゴが着地する少し前から
        el.querySelector('.logo__flash')
          .style.setProperty('--flash-at', (s.at + 0.45) + 's');
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
    var life = 11 + Math.random() * 9;

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
      timer = setTimeout(function () { spawn(); loop(); }, 1900 + Math.random() * 2800);
    }());
  }

  // ---------------------------------------------------------
  // 流れ星。空の上半分を、ときどき一筋だけ横切る
  // ---------------------------------------------------------
  var starTimer = null;

  function shootingStar() {
    if (document.hidden) { return; }
    var rect = stage.getBoundingClientRect();
    if (!rect.width) { return; }

    var el = document.createElement('span');
    el.className = 'meteor';

    var toLeft = Math.random() < 0.4;                 // まれに逆向きへ流れる
    var deg = 17 + Math.random() * 16;                // 下向きの角度
    var len = (11 + Math.random() * 10) / 100;        // 尾の長さ（画面幅に対する比）
    var travel = (26 + Math.random() * 20) / 100;     // 流れる距離

    el.style.width = (len * 100).toFixed(1) + '%';
    el.style.top = (4 + Math.random() * 26).toFixed(1) + '%';
    el.style.left = toLeft
      ? (52 + Math.random() * 34).toFixed(1) + '%'
      : (4 + Math.random() * 26).toFixed(1) + '%';

    el.style.setProperty('--rot', (toLeft ? 180 - deg : deg) + 'deg');
    el.style.setProperty('--travel', (travel * rect.width).toFixed(0) + 'px');
    el.style.setProperty('--peak', (0.45 + Math.random() * 0.3).toFixed(2));
    el.style.animationDuration = (0.95 + Math.random() * 0.6).toFixed(2) + 's';

    el.addEventListener('animationend', function () { el.remove(); });
    motes.appendChild(el);
  }

  function startStars() {
    if (reduceMotion) { return; }
    (function loop(first) {
      var wait = first ? 5000 + Math.random() * 7000 : 17000 + Math.random() * 21000;
      starTimer = setTimeout(function () {
        shootingStar();
        // たまに続けてもう一筋
        if (Math.random() < 0.28) {
          setTimeout(shootingStar, 900 + Math.random() * 1600);
        }
        loop(false);
      }, wait);
    }(true));
  }

  // ---------------------------------------------------------
  // BGM
  //   入口に触れた瞬間に「鳴らしてよい」ことを確かめ（＝解錠）、
  //   黒画面が明ける AUDIO_AT で頭から流しはじめる。
  //   曲は 48.9 秒の繰り返し。いつ音を入れ直しても頭から流す。
  // ---------------------------------------------------------
  var AUDIO_AT = 3.90;       // 曲を鳴らしはじめる時刻（黒画面が明けるところ）
  var VOLUME = 0.92;         // 曲そのものが控えめなので、ほぼそのままの大きさで
  var FADE = 1.6;            // 音量を上げきるまでの秒数
  var STORE = 'ff-sound';

  var audio = document.getElementById('bgm');
  var soundBtn = document.getElementById('sound');
  var fadeTimer = null;
  var waitTimer = null;
  var wanted = false;        // 利用者が音を望んでいるか

  function elapsed() {
    return window.__heroStart ? (performance.now() - window.__heroStart) / 1000 : 0;
  }

  function fadeTo(target, seconds) {
    clearInterval(fadeTimer);
    var from = audio.volume;
    var t0 = performance.now();
    fadeTimer = setInterval(function () {
      var k = Math.min(1, (performance.now() - t0) / (seconds * 1000));
      audio.volume = from + (target - from) * k;
      if (k >= 1) {
        clearInterval(fadeTimer);
        fadeTimer = null;
        if (target === 0) { audio.pause(); }
      }
    }, 40);
  }

  function playFromTop() {
    audio.volume = 0;

    // 頭出しは、曲の長さが分かってからでないと効かない。
    // 音量を 0 にしたまま鳴らしはじめ、頭に戻してから上げる。
    function rewindAndRaise() {
      try { audio.currentTime = 0; } catch (e) { /* 動かせなければそのまま */ }
      fadeTo(VOLUME, FADE);
    }

    var p = audio.play();
    if (p && p.catch) {
      p.catch(function () { setSound(false, false); });  // 鳴らせなかったら消音に戻す
    }

    if (audio.readyState >= 1) {
      rewindAndRaise();
    } else {
      audio.addEventListener('loadedmetadata', rewindAndRaise, { once: true });
    }
  }

  function startAudio() {
    clearTimeout(waitTimer);
    var t = elapsed();

    if (t < AUDIO_AT) {
      // まだ黒画面。明けるのを待ってから鳴らしはじめる
      waitTimer = setTimeout(function () {
        if (wanted) { playFromTop(); }
      }, (AUDIO_AT - t) * 1000);
      return;
    }
    playFromTop();
  }

  function setSound(on, remember) {
    wanted = on;
    soundBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
    soundBtn.setAttribute('aria-label', on ? '音を止める' : '音を鳴らす');
    // ブラウザに止められただけのときは覚えない（次に開いたらまた試す）
    if (remember !== false) {
      try { localStorage.setItem(STORE, on ? '1' : '0'); } catch (e) { /* 使えなくても困らない */ }
    }

    if (on) {
      startAudio();
    } else {
      clearTimeout(waitTimer);
      if (!audio.paused) { fadeTo(0, 0.5); }
    }
  }

  if (audio && soundBtn) {
    soundBtn.addEventListener('click', function () { setSound(!wanted); });
  }

  /* 音の解錠。
     iOS は「利用者が触れた、その処理の中で」play() を呼ばないと鳴らしてくれない。
     待ってから鳴らすのでは遅いので、触れた瞬間に音量 0 のまま鳴らしはじめ、
     時間が来たら頭に戻して音量を上げる。 */
  function unlockAudio() {
    if (!audio) { return; }
    audio.volume = 0;
    var p = audio.play();
    if (p && p.catch) { p.catch(function () { setSound(false, false); }); }
  }

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
      clearTimeout(timer);
      clearTimeout(starTimer);
      timer = null;
      starTimer = null;
      if (wanted && !audio.paused) { audio.pause(); }
    } else {
      if (!timer && !reduceMotion && document.body.classList.contains('is-settled')) {
        startMotes();
        startStars();
      }
      if (wanted && audio.paused) {
        audio.volume = 0;
        var p = audio.play();
        if (p && p.catch) { p.catch(function () { /* 戻れなければそのまま */ }); }
        // まだ黒画面のうちなら、音量は 0 のまま待たせる
        if (elapsed() >= AUDIO_AT) { fadeTo(VOLUME, 0.8); }
      }
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
        window.__star = shootingStar;               // 表示確認用

        setTimeout(startMotes, MOTES_AT * 1000);
        setTimeout(startStars, SETTLE_AT * 1000);
        setTimeout(function () {
          document.body.classList.add('is-settled');
        }, SETTLE_AT * 1000);
      });
    });
  }

  var started = false;
  function begin() {
    if (started) { return; }
    started = true;
    document.body.classList.add('is-started');
    run();
  }

  // 黒画面を読んでもらっているあいだに、絵をそろえておく
  (function preload() {
    ['scene', 'crest', 'logo', 'lead1', 'lead2', 'date', 'coming'].forEach(function (n) {
      new Image().src = 'assets/img/hero/' + n + '.webp';
    });
  }());

  // ---------------------------------------------------------
  // 入口。ここに触れたところから物語がはじまる
  // ---------------------------------------------------------
  var gate = document.getElementById('gate');
  var gateBtn = document.getElementById('gateBtn');

  if (reduceMotion) {
    if (gate) { gate.remove(); }
    begin();
  } else if (gateBtn) {
    gateBtn.addEventListener('click', function () {
      if (started) { return; }

      // 前回わざわざ消音にした人には、そのまま静かに見せる
      var muted = false;
      try { muted = localStorage.getItem(STORE) === '0'; } catch (e) { /* 使えなくても困らない */ }

      if (!muted) {
        unlockAudio();        // 触れたこの場で鳴らしはじめないと、iOS は許してくれない
        setSound(true);       // 音量を上げるのは AUDIO_AT から
      }
      begin();
    });
  } else {
    begin();                  // 入口が見つからないときは、そのまま始める
  }

  // ---------------------------------------------------------
  // PWA
  // ---------------------------------------------------------
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('sw.js').catch(function () { /* 表示には影響しない */ });
    });
  }
}());
