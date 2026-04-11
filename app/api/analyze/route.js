import { GoogleGenAI } from '@google/genai';

export async function POST(req) {
  try {
    const body = await req.json();
    const { image, apiKey, provider = "gemini", ollamaUrl = "http://192.168.1.222:11434", ollamaModel = "gemma4:e4b" } = body;

    if (!image) {
      return new Response(JSON.stringify({ error: "No image provided" }), { status: 400 });
    }

    const match = image.match(/^data:(image\/\w+);base64,(.*)$/);
    if (!match) {
      return new Response(JSON.stringify({ error: "Invalid image format" }), { status: 400 });
    }

    const mimeType = match[1];
    const base64Data = match[2];

    const prompt = `
You are a professional colorist and photo editor. 
Analyze the aesthetic, lighting, and mood of the provided benchmark image.
I need to apply matching CSS filters to a target image to achieve a similar look.

Please output the recommended CSS filter values as a strict JSON object with these exact keys:
- "brightness": An integer from 0 to 200 (100 is neutral, no change).
- "contrast": An integer from 0 to 200 (100 is neutral).
- "saturation": An integer from 0 to 200 (100 is neutral).
- "sepia": An integer from 0 to 100 (0 is neutral).
- "hueRotate": An integer from -180 to 180 (0 is neutral).

Make the analysis realistic. If the image is dark and moody, lower brightness and maybe add contrast. If it has a vintage feel, increase sepia, etc.

Return ONLY the raw JSON object, without markdown formatting. Example:
{
  "brightness": 110,
  "contrast": 120,
  "saturation": 80,
  "sepia": 20,
  "hueRotate": 0
}
    `;

    let filters;

    if (provider === "ollama") {
      // OLLAMA LOGIC
      // Strip trailing slashes from URL
      const cleanUrl = ollamaUrl.replace(/\/$/, "");
      
      const ollamaRes = await fetch(`${cleanUrl}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: ollamaModel, 
          prompt: prompt,
          images: [base64Data],
          stream: false,
          format: "json" // Guarantees JSON output if supported by model
        })
      });

      if (!ollamaRes.ok) {
        throw new Error(`Ollama API error: ${ollamaRes.status} ${ollamaRes.statusText}`);
      }

      const ollamaData = await ollamaRes.json();
      const textOutput = ollamaData.response || "";
      
      try {
        filters = JSON.parse(textOutput);
      } catch (e) {
        console.error("Local model did not return pure JSON:", textOutput);
        throw new Error("Local model failed to generate valid JSON format.");
      }

    } else {
      // GEMINI LOGIC
      const keyToUse = apiKey || process.env.GEMINI_API_KEY;
      if (!keyToUse) {
         return new Response(JSON.stringify({ error: "Gemini API key is required." }), { status: 401 });
      }

      const ai = new GoogleGenAI({ apiKey: keyToUse });
      
      const response = await ai.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: [
          prompt,
          {
            inlineData: {
              data: base64Data,
              mimeType: mimeType
            }
          }
        ]
      });

      const textOutput = response.text || "";
      const cleanJson = textOutput.replace(/```json/g, '').replace(/```/g, '').trim();
      
      try {
        filters = JSON.parse(cleanJson);
      } catch (err) {
        console.error("Failed to parse Gemini output:", cleanJson);
        throw new Error("Gemini failed to generate valid JSON format.");
      }
    }

    // Fallback sanity check for variables mapping
    if (!filters || typeof filters.brightness !== 'number') {
      filters = { brightness: 100, contrast: 100, saturation: 100, sepia: 0, hueRotate: 0 };
    }

    return new Response(JSON.stringify({ filters }), { status: 200 });

  } catch (error) {
    console.error("Error analyzing image:", error);
    return new Response(JSON.stringify({ error: "Internal server error during analysis. " + error.message }), { status: 500 });
  }
}
