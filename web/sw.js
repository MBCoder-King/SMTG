self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open('smtg-cache-v1').then((cache) => {
      return cache.addAll(['/', '/styles.css', '/script.js', '/manifest.webmanifest']);
    })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
