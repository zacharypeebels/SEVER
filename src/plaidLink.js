// SEVER — Plaid Link loader. Loads Plaid's script on demand and wraps the
// Link flow in a promise. The publicToken it yields is short-lived and only
// exchanged server-side; no bank credentials ever touch SEVER code.

let scriptPromise = null;

function loadPlaid() {
  if (window.Plaid) return Promise.resolve(window.Plaid);
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://cdn.plaid.com/link/v2/stable/link-initialize.js";
    s.onload = () => resolve(window.Plaid);
    s.onerror = () => {
      scriptPromise = null;
      reject(new Error("Plaid Link failed to load"));
    };
    document.head.appendChild(s);
  });
  return scriptPromise;
}

export async function openPlaidLink(linkToken) {
  const Plaid = await loadPlaid();
  return new Promise((resolve, reject) => {
    const handler = Plaid.create({
      token: linkToken,
      onSuccess: (publicToken, metadata) =>
        resolve({
          publicToken,
          institution: metadata?.institution?.name || "Linked bank",
        }),
      onExit: (err) => reject(err || new Error("link-cancelled")),
    });
    handler.open();
  });
}
