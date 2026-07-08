// SEVER — Cognito auth glue (prepped, dormant until AWS is ready).
//
// Activation: set the three VITE_COGNITO_* values in the Pages build
// (or a .env.production file) once the user pool exists. While they are
// unset, isAuthConfigured() returns false and the app runs in open
// beta-preview mode with mock data.

const domain = import.meta.env.VITE_COGNITO_DOMAIN; // e.g. sever-beta.auth.us-east-1.amazoncognito.com
const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID;
const redirectUri = import.meta.env.VITE_COGNITO_REDIRECT_URI; // e.g. https://zacharypeebels.github.io/SEVER/

const TOKEN_KEY = "sever.tokens";

export function isAuthConfigured() {
  return Boolean(domain && clientId && redirectUri);
}

export function loginUrl() {
  const params = new URLSearchParams({
    response_type: "code",
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: "openid email",
  });
  return `https://${domain}/oauth2/authorize?${params}`;
}

export function logout() {
  sessionStorage.removeItem(TOKEN_KEY);
  if (!isAuthConfigured()) return;
  const params = new URLSearchParams({ client_id: clientId, logout_uri: redirectUri });
  window.location.href = `https://${domain}/logout?${params}`;
}

export function getTokens() {
  const raw = sessionStorage.getItem(TOKEN_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function getAccessToken() {
  return getTokens()?.access_token ?? null;
}

// Decoded ID-token claims (email, sub) for profile display. Display only —
// authorization always happens server-side against the signed access token.
export function getIdClaims() {
  const idToken = getTokens()?.id_token;
  if (!idToken) return null;
  try {
    const payload = idToken.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(payload));
  } catch {
    return null;
  }
}

export function passwordResetUrl() {
  const params = new URLSearchParams({
    client_id: clientId,
    response_type: "code",
    scope: "openid email",
    redirect_uri: redirectUri,
  });
  return `https://${domain}/forgotPassword?${params}`;
}

// Handle the ?code=... redirect back from the Cognito Hosted UI.
export async function completeLoginFromRedirect() {
  const code = new URLSearchParams(window.location.search).get("code");
  if (!code || !isAuthConfigured()) return false;

  const res = await fetch(`https://${domain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: clientId,
      redirect_uri: redirectUri,
      code,
    }),
  });
  if (!res.ok) return false;

  sessionStorage.setItem(TOKEN_KEY, JSON.stringify(await res.json()));
  window.history.replaceState({}, "", window.location.pathname); // strip ?code=
  return true;
}

// Attach to API calls: fetch(url, { headers: authHeaders() })
export function authHeaders() {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
