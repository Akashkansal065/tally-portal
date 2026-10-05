self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// Push notification event listener
self.addEventListener('push', (event) => {
  if (!event.data) return;

  try {
    const payload = event.data.json();
    const title = payload.title || 'MyTally Alert';
    const options = {
      body: payload.body || '',
      icon: payload.icon || '/icon-192.png',
      badge: payload.badge || '/icon-192.png',
      vibrate: [200, 100, 200],
      tag: payload.tag || 'mytally-alert',
      renotify: true,
      requireInteraction: false,
      data: payload.data || { url: '/admin' },
    };
    event.waitUntil(
      self.registration.showNotification(title, options)
    );
  } catch (e) {
    event.waitUntil(
      self.registration.showNotification('MyTally Alert', {
        body: event.data.text(),
        icon: '/icon-192.png',
        badge: '/icon-192.png',
        tag: 'mytally-raw-alert',
        renotify: true,
      })
    );
  }
});

// Notification click: open the app at the notification. An already-open app window is brought forward and
// sent there (in-app navigation if the page answers, otherwise a normal page load); only with no window open
// is a new one started. Matching on the exact URL used to open duplicate windows that never navigated.
function askPageToNavigate(client, url) {
  return new Promise((resolve) => {
    const channel = new MessageChannel();
    const timer = setTimeout(() => resolve(false), 1000);
    channel.port1.onmessage = () => {
      clearTimeout(timer);
      resolve(true);
    };
    client.postMessage({ type: 'mytally:navigate', url }, [channel.port2]);
  });
}

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || '/notifications', self.location.origin).href;

  event.waitUntil((async () => {
    const windows = await clients.matchAll({ type: 'window', includeUncontrolled: true });
    const client = windows.find((c) => new URL(c.url).origin === self.location.origin);
    if (!client) {
      if (clients.openWindow) await clients.openWindow(target);
      return;
    }
    try {
      await client.focus();
    } catch (e) {
      // Some browsers only allow focus in certain states; navigation still works
    }
    if (await askPageToNavigate(client, target)) return;
    if ('navigate' in client) {
      try {
        await client.navigate(target);
        return;
      } catch (e) {
        // Uncontrolled windows can't be navigated by the worker
      }
    }
    if (clients.openWindow) await clients.openWindow(target);
  })());
});
