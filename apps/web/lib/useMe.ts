"use client";

import { useEffect, useState } from "react";
import { apiGet, ApiError } from "./api";

export type Me = {
  id: string;
  email: string;
  role: "user" | "contributor" | "admin";
  state: string;
  display_name: string | null;
  photo_url: string | null;
  profile_slug: string | null;
};

let _cache: { me: Me | null; ts: number } | null = null;
const listeners = new Set<(m: Me | null) => void>();

export function setMe(me: Me | null) {
  _cache = { me, ts: Date.now() };
  listeners.forEach((l) => l(me));
}

export function useMe(): { me: Me | null; loading: boolean; refresh: () => void } {
  const [me, setLocal] = useState<Me | null>(_cache?.me ?? null);
  const [loading, setLoading] = useState(_cache === null);

  useEffect(() => {
    const onChange = (m: Me | null) => setLocal(m);
    listeners.add(onChange);
    if (_cache === null) {
      apiGet<Me>("/auth/me")
        .then((m) => setMe(m))
        .catch((e) => {
          if (e instanceof ApiError && e.status === 401) {
            setMe(null);
          } else {
            // network or other — treat as unauthenticated for UI purposes
            setMe(null);
          }
        })
        .finally(() => setLoading(false));
    }
    return () => {
      listeners.delete(onChange);
    };
  }, []);

  return {
    me,
    loading,
    refresh: () => {
      _cache = null;
      apiGet<Me>("/auth/me")
        .then((m) => setMe(m))
        .catch(() => setMe(null));
    },
  };
}
