// Server Component — Tauri static export requires generateStaticParams here.
// dynamicParams = false: skip all unmatched dynamic routes (client-side routing handles them).
import ClientPage from './_client';

export const dynamicParams = false;

export function generateStaticParams() {
  return []; // No pre-rendered pages; Tauri router handles navigation client-side
}

export default ClientPage;
