// Auth route stub — works for both dev (no Azure AD configured) and Tauri builds.
// Returns minimal valid JSON responses so NextAuth client doesn't crash.
export const dynamic = 'force-dynamic';

export function generateStaticParams() {
  return [{ nextauth: ['session'] }, { nextauth: ['csrf'] }];
}

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const path = url.pathname;

  if (path.endsWith('/session')) {
    return Response.json(null); // no session = not authenticated
  }
  if (path.endsWith('/csrf')) {
    return Response.json({ csrfToken: 'dev-stub' });
  }
  if (path.endsWith('/providers')) {
    return Response.json({});
  }
  return Response.json({ error: 'not_configured' }, { status: 404 });
}

export async function POST(req: Request): Promise<Response> {
  return Response.json({ error: 'not_configured' }, { status: 404 });
}
