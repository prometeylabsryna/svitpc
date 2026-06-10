/**
 * Web Push subscription module.
 * Reads VAPID public key from <meta name="vapid-pub">,
 * registers service worker, subscribes, POSTs to /notifications/subscribe/.
 */

const VAPID_META = "vapid-pub";

const urlBase64ToUint8Array = (base64String) => {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
};

export const initPushNotifications = async () => {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    return;
  }

  const vapidMeta = document.querySelector(`meta[name="${VAPID_META}"]`);
  const vapidPublicKey = vapidMeta?.content;
  if (!vapidPublicKey) return;

  try {
    const registration = await navigator.serviceWorker.register("/sw.js", { scope: "/" });

    const existingSubscription = await registration.pushManager.getSubscription();
    if (existingSubscription) return;  // already subscribed

    const permission = await Notification.requestPermission();
    if (permission !== "granted") return;

    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
    });

    await fetch("/notifications/subscribe/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": document.querySelector('meta[name="csrf-token"]')?.content ?? "",
      },
      body: JSON.stringify(subscription.toJSON()),
    });
  } catch (err) {
    console.error("Push init error:", err);
  }
};
