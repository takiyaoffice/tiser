/* 仙台への冒険 ティザー ─ オフラインでも起動画面として成立させるための最小構成 */
'use strict';

var CACHE = 'future-fantasy-v9';

var ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './assets/css/hero.css',
  './assets/js/hero.js',
  './assets/img/clouds.png',
  './assets/img/hero/tap.webp',
  './assets/img/hero/scene.webp',
  './assets/img/hero/crest.webp',
  './assets/img/hero/logo.webp',
  './assets/img/hero/lead1.webp',
  './assets/img/hero/lead2.webp',
  './assets/img/hero/date.webp',
  './assets/img/hero/coming.webp',
  './assets/img/icon-192.png',
  './assets/img/icon-512.png',
  './assets/img/apple-touch-icon.png',
  './assets/img/favicon.png'
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE)
      .then(function (cache) { return cache.addAll(ASSETS); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(keys.map(function (key) {
          return key === CACHE ? null : caches.delete(key);
        }));
      })
      .then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (event) {
  if (event.request.method !== 'GET') { return; }

  // 音は途中から取りに来る（Range 要求）ことがあるので、ここでは触らない
  if (/\.mp3($|\?)/.test(event.request.url) || event.request.headers.has('range')) { return; }

  event.respondWith(
    caches.match(event.request).then(function (hit) {
      if (hit) { return hit; }

      return fetch(event.request).then(function (res) {
        if (res && res.status === 200 && res.type === 'basic') {
          var copy = res.clone();
          caches.open(CACHE).then(function (cache) { cache.put(event.request, copy); });
        }
        return res;
      }).catch(function () {
        return caches.match('./index.html');
      });
    })
  );
});
