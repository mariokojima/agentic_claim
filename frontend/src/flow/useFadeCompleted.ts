import { useEffect, useMemo, useRef, useState } from "react";
import type { NodeState } from "./status";

/** Tempo que um nó/tool permanece verde (concluído) antes de voltar à cor original. */
export const FADE_COMPLETED_MS = 2000;

/**
 * Faz nós concluídos voltarem a "idle" após `ms`. Atenção/erro permanecem visíveis.
 * Cada nó tem seu próprio timer, reiniciado apenas quando o status daquele nó muda.
 */
export function useFadeCompleted(
  statuses: Record<string, NodeState>,
  ms: number = FADE_COMPLETED_MS,
): Record<string, NodeState> {
  const [faded, setFaded] = useState<ReadonlySet<string>>(new Set());
  const prev = useRef<Record<string, NodeState>>({});
  const timers = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    const changed: string[] = [];
    for (const [key, state] of Object.entries(statuses)) {
      if (prev.current[key]?.status !== state.status) changed.push(key);
    }
    const removed = Object.keys(prev.current).filter((key) => !(key in statuses));
    prev.current = statuses;
    if (changed.length === 0 && removed.length === 0) return;

    for (const key of [...changed, ...removed]) {
      window.clearTimeout(timers.current.get(key));
      timers.current.delete(key);
    }
    setFaded((current) => {
      const next = new Set(current);
      for (const key of [...changed, ...removed]) next.delete(key);
      return next;
    });
    for (const key of changed) {
      if (statuses[key].status !== "completed") continue;
      const timer = window.setTimeout(() => {
        timers.current.delete(key);
        setFaded((current) => new Set(current).add(key));
      }, ms);
      timers.current.set(key, timer);
    }
  }, [statuses, ms]);

  useEffect(() => {
    const pending = timers.current;
    return () => {
      for (const timer of pending.values()) window.clearTimeout(timer);
    };
  }, []);

  return useMemo(() => {
    if (faded.size === 0) return statuses;
    const result: Record<string, NodeState> = {};
    for (const [key, state] of Object.entries(statuses)) {
      result[key] = faded.has(key) ? { status: "idle", detail: state.detail } : state;
    }
    return result;
  }, [statuses, faded]);
}
