/* 仙台への冒険 ティザー ─ オフラインでも起動画面として成立させるための最小構成 */
'use strict';

var CACHE = 'sendai-teaser-v1';

var ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './assets/css/teaser.css',
  './assets/js/teaser.js',
  './assets/img/teaser.webp',
  './assets/img/teaser.png',
  './assets/img/clouds.png',
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

  event.respondWith(
    caches.match(event.request).then(function (hit) {
      if (hit) { return hit; }

      return fetch(event.request).then(function (res) {
        if (res && res.ok && res.type === 'basic') {
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
