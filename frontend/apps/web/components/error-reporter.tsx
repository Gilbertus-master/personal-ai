"use client";

import { useEffect, useRef } from "react";

/**
 * Global error reporter — catches ALL unhandled JS/React errors
 * and sends them to the Gilbertus backend for autofix processing.
 * Renders nothing.
 */
export function ErrorReporter({ userId = "sebastian" }: { userId?: string }) {
  const recentRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    // Derive API URL from current page host (works on localhost, WSL2 IP, etc.)
    const API = `http://${window.location.hostname}:8000`;

    const report = async (data: Record<string, unknown>) => {
      // Deduplicate: don't report same error within 60s
      const key = `${data.error_type}:${String(data.error_message).slice(0, 100)}`;
      if (recentRef.current.has(key)) return;
      recentRef.current.add(key);
      setTimeout(() => recentRef.current.delete(key), 60_000);

      try {
        await fetch(`${API}/errors/report`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: userId,
            app_version: "0.2",
            browser: navigator.userAgent.slice(0, 120),
            ...data,
          }),
        });
      } catch {
        // never crash the reporter itself
      }
    };

    // 1. Unhandled JS errors (TypeError, ReferenceError, SyntaxError, etc.)
    const onError = (event: ErrorEvent) => {
      report({
        error_type: "runtime",
        error_message: event.message?.slice(0, 500),
        error_stack: event.error?.stack?.slice(0, 1000),
        component: event.filename?.split("/").pop(),
        module: event.filename,
        route: window.location.pathname,
      });
    };

    // 2. Unhandled Promise rejections (failed fetch, async errors)
    const onUnhandledRejection = (event: PromiseRejectionEvent) => {
      const reason = event.reason;
      const message =
        reason instanceof Error
          ? reason.message
          : String(reason);
      const stack =
        reason instanceof Error
          ? reason.stack?.slice(0, 1000)
          : undefined;

      report({
        error_type: "network",
        error_message: message.slice(0, 500),
        error_stack: stack,
        route: window.location.pathname,
      });
    };

    // 3. Console.error interceptor — catch React and framework errors
    const originalConsoleError = console.error;
    console.error = (...args: unknown[]) => {
      originalConsoleError(...args);
      const msg = args.map((a) =>
        a instanceof Error ? a.message : String(a)
      ).join(" ");

      // Skip React internal noise that's not actionable
      if (
        msg.includes("Warning:") ||
        msg.includes("Minified React error") ||
        msg.includes("hydration") ||
        msg.includes("act()") ||
        msg.includes("same key") ||
        msg.includes("Non-unique keys") ||
        msg.includes("Encountered two children")
      ) {
        return;
      }

      // Report anything that looks like an error
      if (
        msg.includes("Error") ||
        msg.includes("error") ||
        msg.includes("Cannot") ||
        msg.includes("is not") ||
        msg.includes("undefined") ||
        msg.includes("null") ||
        msg.includes("failed") ||
        msg.includes("Failed") ||
        msg.includes("CORS") ||
        msg.includes("refused") ||
        msg.includes("timeout") ||
        msg.includes("Unexpected") ||
        msg.includes("500") ||
        msg.includes("404")
      ) {
        report({
          error_type: "render",
          error_message: msg.slice(0, 500),
          error_stack: new Error().stack?.slice(0, 500),
          route: window.location.pathname,
        });
      }
    };

    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onUnhandledRejection);

    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onUnhandledRejection);
      console.error = originalConsoleError;
    };
  }, [userId]);

  return null;
}
