// Tauri static export: NextAuth not needed in desktop app.
// generateStaticParams required for dynamic API routes in output: 'export'.
export const dynamic = 'force-static';

export function generateStaticParams() {
  return [{ nextauth: ['session'] }, { nextauth: ['csrf'] }];
}

export async function GET(_req: Request): Promise<Response> {
  return new Response(null, { status: 404 });
}

export async function POST(_req: Request): Promise<Response> {
  return new Response(null, { status: 404 });
}
