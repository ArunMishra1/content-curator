// Server-side proxy to the FastAPI backend's /discover endpoint.
// See recommend/route.js for why this proxy pattern exists (key stays server-side).

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
    const backendResponse = await fetch(`${backendUrl}/discover`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
      },
      body: JSON.stringify(body),
    });

    const data = await backendResponse.json();

    if (!backendResponse.ok) {
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
