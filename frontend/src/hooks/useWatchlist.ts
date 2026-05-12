import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "nie.watchlist";

interface WatchlistEntry {
  id: string;
  productName: string;
  addedAt: number;
  verdict?: string;
}

function loadWatchlist(): WatchlistEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveWatchlist(list: WatchlistEntry[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    // ignore quota / serialization errors — localStorage is best-effort for a demo
  }
}

function makeEntryId(productName: string): string {
  return `${productName}-${Math.floor(Date.now() / 60000)}`;
}

/**
 * Simulated watchlist backed by localStorage. Supports toggling an item
 * on/off for the current submission; `isOn` is keyed off the product name
 * plus a coarse time bucket so revisiting the same submission within a
 * minute keeps the toggle state.
 */
export function useWatchlist(productName: string | undefined) {
  const [list, setList] = useState<WatchlistEntry[]>(() => loadWatchlist());

  const entryId = productName ? makeEntryId(productName) : null;
  const isOn = entryId ? list.some((e) => e.id === entryId) : false;

  useEffect(() => {
    saveWatchlist(list);
  }, [list]);

  const add = useCallback(
    (verdict?: string) => {
      if (!productName || !entryId) return;
      setList((prev) =>
        prev.some((e) => e.id === entryId)
          ? prev
          : [...prev, { id: entryId, productName, addedAt: Date.now(), verdict }],
      );
    },
    [entryId, productName],
  );

  const remove = useCallback(() => {
    if (!entryId) return;
    setList((prev) => prev.filter((e) => e.id !== entryId));
  }, [entryId]);

  const toggle = useCallback(
    (verdict?: string) => {
      if (isOn) remove();
      else add(verdict);
    },
    [isOn, add, remove],
  );

  return { isOn, toggle, count: list.length };
}
