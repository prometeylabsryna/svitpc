/* SvitPC Service Worker — push notifications */

const CACHE_NAME = "svitpc-v1";

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { title: "СвітПК", body: event.data ? event.data.text() : "" };
  }
  const title = data.title || "СвітПК";
  const options = {
    body: data.body || "",
    icon: data.icon || "/static/images/icons/icon-192.png",
    badge: data.badge || "/static/images/icons/badge-72.png",
    data: { url: data.url || "/" },
    tag: data.tag || "svitpc-notification",
    renotify: true,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url === url && "focus" in client) {
          return client.focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});
