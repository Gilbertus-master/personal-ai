// Server Component wrapper for Tauri static export.
// generateStaticParams must live in a Server Component (not 'use client').
export function generateStaticParams() {
  return []; // Tauri: all dynamic routes loaded client-side
}

export { default } from './_client';
