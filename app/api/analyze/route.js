import { aiEngine } from '@/lib/services/ai-engine';

export async function POST(req) {
  try {
    const body = await req.json();
    const { image, apiKey, provider = "gemini", ollamaUrl = process.env.NEXT_PUBLIC_OLLAMA_URL || "http://localhost:11434", ollamaModel = "gemma4:e4b" } = body;

    if (!image) {
      return new Response(JSON.stringify({ error: "No image provided" }), { status: 400 });
    }

    const result = await aiEngine.analyzeStyle(image, {
      provider, apiKey, ollamaUrl, ollamaModel,
    });

    return new Response(JSON.stringify({
      filters: result.filters,
      cbState: result.cbState,
    }), { status: 200 });

  } catch (error) {
    console.error("Error analyzing image:", error);

    // Gemini Refinement #4: Surface circuit breaker state in error responses
    const isCircuitOpen = error.message?.includes("Circuit breaker is OPEN");
    const status = isCircuitOpen ? 503 : 500;
    const errorMsg = isCircuitOpen
      ? "Service temporarily unavailable. The AI provider is experiencing issues. Please try again shortly."
      : "Internal server error during analysis. " + error.message;

    return new Response(JSON.stringify({
      error: errorMsg,
      cbState: isCircuitOpen ? "OPEN" : undefined,
    }), { status });
  }
}
