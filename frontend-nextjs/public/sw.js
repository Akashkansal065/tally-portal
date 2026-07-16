const CACHE_NAME = 'tally-web-cache-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // Pass through all fetch events since it's a dynamic Next.js app,
  // this basic SW just enables the "Install App" prompt.
});

// Push notification event listener
self.addEventListener('push', (event) => {
  if (event.data) {
    try {
      const payload = event.data.json();
      const options = {
        body: payload.body,
        icon: payload.icon || '/icon-192.png',
        badge: payload.badge || '/icon-192.png',
        vibrate: [100, 50, 100],
        data: payload.data || {}
      };
      event.waitUntil(
        self.registration.showNotification(payload.title, options)
      );
    } catch (e) {
      event.waitUntil(
        self.registration.showNotification('Sneh Distributors Portal', {
          body: event.data.text(),
          icon: '/icon-192.png',
          badge: '/icon-192.png'
        })
      );
    }
  }
});

// Notification click event listener
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const urlToOpen = event.notification.data?.url || '/admin';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (let i = 0; i < windowClients.length; i++) {
        const client = windowClients[i];
        if (client.url.includes(urlToOpen) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});
