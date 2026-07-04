// Server-side proxy to the FastAPI backend's /recommend endpoint.
//
// This route runs on the server (Next.js server, not the browser), so
// CURATOR_API_KEY is read from a server-only environment variable here and
// attached to the outgoing request. The browser calling THIS route never
// sees the real key -- it only ever talks to our own /api/recommend.

export async function POST(request) {
  const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
  const apiKey = process.env.CURATOR_API_KEY;

  if (!apiKey) {
    return Response.json(
      { error: "Server misconfiguration: CURATOR_API_KEY is not set in the frontend's environment." },
      { status: 500 }
    );
  }

  const body = await request.json();

  try {
    const backendResponse = await fetch(`${backendUrl}/recommend`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
      },
      body: JSON.stringify(body),
    });

    const data = await backendResponse.json();

    if (!backendResponse.ok) {
      // Forward the backend's actual error detail rather than a generic message,
      // so the UI can show something meaningful (e.g. "Invalid API key", "429 rate limited").
      return Response.json({ error: data.detail || "Backend returned an error." }, { status: backendResponse.status });
    }

    return Response.json(data);
  } catch (err) {
    return Response.json(
      { error: `Could not reach the backend at ${backendUrl}. Is it running?` },
      { status: 502 }
    );
  }
}
