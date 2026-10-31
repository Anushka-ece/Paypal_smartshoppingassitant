"use client";

import { useCallback, useEffect, useState } from "react";

const SESSION_KEY = "pennypilot_session_v1";

type Session = { token: string; role: string };

export function useSession() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const saved = window.sessionStorage.getItem(SESSION_KEY);
      if (saved) setSession(JSON.parse(saved) as Session);
    } catch {
      window.sessionStorage.removeItem(SESSION_KEY);
    } finally {
      setReady(true);
    }
  }, []);

  const save = useCallback((next: Session) => {
    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(next));
    setSession(next);
  }, []);

  const clear = useCallback(() => {
    window.sessionStorage.removeItem(SESSION_KEY);
    setSession(null);
  }, []);

  return { session, ready, save, clear };
}
