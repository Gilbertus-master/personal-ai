"use client";

import { useEffect } from "react";

/**
 * Global error reporter — catches ALL unhandled JS/React errors
 * and sends them to the Gilbertus backend for autofix processing.
 * Renders nothing.
 */
export function ErrorReporter({ userId = "sebastian" }: { userId?: string }) {
  useEffect(() => {
    const API =
      process.env.NEXT_PUBLIC_GILBERTUS_API_URL || "http://127.0.0.1:8000";

    const report = async (data: Record<string, unknown>) => {
      try {
        await fetch(`${API}/errors/report`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: userId, ...data }),
        });
      } catch {
        // never crash the reporter itself
      }
    };

    // 1. Unhandled JS errors
    const onError = (event: ErrorEvent) => {
      report({
        error_type: "runtime",
        error_message: event.message,
        error_stack: event.error?.stack?.slice(0, 500),
        component: event.filename?.split("/").pop(),
        route: window.location.pathname,
        browser: navigator.userAgent.slice(0, 100),
      });
    };

    // 2. Unhandled Promise rejections
    const onUnhandledRejection = (event: PromiseRejectionEvent) => {
      report({
        error_type: "network",
        error_message: String(event.reason).slice(0, 500),
        route: window.location.pathname,
        browser: navigator.userAgent.slice(0, 100),
      });
    };

    // 3. Console.error interceptor — only meaningful errors
    const originalConsoleError = console.error;
    console.error = (...args: unknown[]) => {
      originalConsoleError(...args);
      const msg = args.map(String).join(" ");
      if (
        msg.includes("Error:") ||
        msg.includes("TypeError") ||
        msg.includes("Cannot read")
      ) {
        report({
          error_type: "render",
          error_message: msg.slice(0, 500),
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
