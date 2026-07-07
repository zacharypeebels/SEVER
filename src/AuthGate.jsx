import React, { useEffect, useState } from "react";
import { completeLoginFromRedirect, getAccessToken, isAuthConfigured, loginUrl } from "./auth.js";

// Gate: shows a sign-in screen when Cognito is configured and the user has
// no session. While Cognito env vars are absent (current beta), it renders
// the app directly in preview mode.
export default function AuthGate({ children }) {
  const [ready, setReady] = useState(!isAuthConfigured());
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    if (!isAuthConfigured()) return;
    completeLoginFromRedirect().finally(() => {
      setAuthed(Boolean(getAccessToken()));
      setReady(true);
    });
  }, []);

  if (!ready) return null;
  if (!isAuthConfigured() || authed) return children;

  return (
    <div style={{
      minHeight: "100vh", display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", gap: 16,
      background: "#EEF2EC", color: "#17221C", fontFamily: "system-ui, sans-serif",
    }}>
      <h1 style={{ margin: 0, letterSpacing: 2 }}>SEVER/</h1>
      <p style={{ color: "#6B776F", margin: 0 }}>Autonomous Subscription Guardian</p>
      <a href={loginUrl()} style={{
        marginTop: 8, padding: "10px 28px", background: "#1E7A4C", color: "#fff",
        borderRadius: 4, textDecoration: "none", fontWeight: 600,
      }}>
        Sign in / Create account
      </a>
    </div>
  );
}
