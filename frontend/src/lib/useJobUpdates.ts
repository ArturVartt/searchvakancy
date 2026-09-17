import { useEffect, useLayoutEffect, useRef } from "react";
import { api } from "./api";
import type { WsEvent } from "../types";

/**
 * Подключается к ws://.../ws/jobs/ (apps/jobs/consumers.py на бэкенде) и
 * зовёт onEvent на каждое new_job/job_updated/job_removed. Автопереподключение
 * с растущей паузой, если соединение оборвалось.
 */
export function useJobUpdates(onEvent: (event: WsEvent) => void): void {
  const onEventRef = useRef(onEvent);
  // Обновляем ref после коммита (не прямо в теле рендера) — иначе рефы,
  // используемые вне рендера, не должны трогаться во время самого рендера.
  useLayoutEffect(() => {
    onEventRef.current = onEvent;
  });

  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;
    let stopped = false;

    function connect() {
      socket = new WebSocket(`${api.wsBaseUrl()}/ws/jobs/`);

      socket.onopen = () => {
        attempt = 0;
      };

      socket.onmessage = (event: MessageEvent<string>) => {
        try {
          const parsed = JSON.parse(event.data) as WsEvent;
          onEventRef.current(parsed);
        } catch {
          // не JSON (например, "pong") — игнорируем
        }
      };

      socket.onclose = () => {
        if (stopped) return;
        const delay = Math.min(1000 * 2 ** attempt, 15000);
        attempt += 1;
        reconnectTimer = setTimeout(connect, delay);
      };

      socket.onerror = () => {
        socket?.close();
      };
    }

    connect();

    return () => {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);
}
