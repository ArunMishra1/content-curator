// Proxies the backend's public /health endpoint. No API key needed here --
// /health is intentionally unauthenticated on the backend too (see the
// FastAPI app's auth.py / main.py for why).

export async function GET() {
  const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";

  try {
    const backendResponse = await fetch(`${backendUrl}/health`, { cache: "no-store" });
    if (!backendResponse.ok) {
      return Response.json({ status: "offline" }, { status: 502 });
    }
    const data = await backendResponse.json();
    return Response.json(data);
  } catch (err) {
    return Response.json({ status: "offline" }, { status: 502 });
  }
}
