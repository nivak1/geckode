"use client";

import * as React from "react";
import type {
  ToastActionElement,
  ToastProps,
} from "@/components/ui/toast";

const TOAST_LIMIT = 4;
const TOAST_REMOVE_DELAY = 4000;

type ToasterToast = ToastProps & {
  id: string;
  title?: React.ReactNode;
  description?: React.ReactNode;
  action?: ToastActionElement;
};

type State = { toasts: ToasterToast[] };

const listeners: Array<(state: State) => void> = [];
let memoryState: State = { toasts: [] };

function dispatch(next: State) {
  memoryState = next;
  for (const listener of listeners) listener(memoryState);
}

function genId() {
  return Math.random().toString(36).slice(2, 10);
}

type Toast = Omit<ToasterToast, "id">;

export function toast(t: Toast) {
  const id = genId();
  const newToast: ToasterToast = {
    ...t,
    id,
    open: true,
    onOpenChange: (open) => {
      if (!open) dismiss(id);
    },
  };
  const next = {
    toasts: [newToast, ...memoryState.toasts].slice(0, TOAST_LIMIT),
  };
  dispatch(next);

  setTimeout(() => dismiss(id), TOAST_REMOVE_DELAY);
  return { id, dismiss: () => dismiss(id) };
}

function dismiss(id: string) {
  dispatch({
    toasts: memoryState.toasts.map((t) =>
      t.id === id ? { ...t, open: false } : t,
    ),
  });
  setTimeout(() => {
    dispatch({ toasts: memoryState.toasts.filter((t) => t.id !== id) });
  }, 250);
}

export function useToast() {
  const [state, setState] = React.useState<State>(memoryState);
  React.useEffect(() => {
    listeners.push(setState);
    return () => {
      const idx = listeners.indexOf(setState);
      if (idx > -1) listeners.splice(idx, 1);
    };
  }, []);
  return { ...state, toast, dismiss };
}
