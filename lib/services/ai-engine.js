/**
 * Antigravity Engine v2.1 — AI Engine Service
 * Shared, hardened AI analysis service with Circuit Breaker resilience.
 *
 * Extracted from app/api/analyze/route.js to enable reuse across
 * the application without coupling to the Next.js route handler.
 *
 * Circuit Breaker Pattern (Gemini Refinement #4):
 *   CLOSED   → Normal operation, requests flow through
 *   OPEN     → Failures exceeded threshold, fast-fail for cooldown period
 *   HALF_OPEN → After cooldown, one probe request tests recovery
 *
 * The analyzeStyle() response includes a cbState flag so the UI can
 * display "Service Temporarily Unavailable" vs generic "Analysis Failed".
 */

import { GoogleGenAI } from "@google/genai";

// ─── Circuit Breaker ────────────────────────────────────────────────

const CB_STATES = Object.freeze({
  CLOSED: "CLOSED",
  OPEN: "OPEN",
  HALF_OPEN: "HALF_OPEN",
});

class CircuitBreaker {
  /**
   * @param {object} opts
   * @param {number} opts.failureThreshold - Consecutive failures before opening
   * @param {number} opts.cooldownMs - How long to stay open before half-open probe
   */
  constructor({ failureThreshold = 3, cooldownMs = 30_000 } = {}) {
    this._failureThreshold = failureThreshold;
    this._cooldownMs = cooldownMs;
    this._state = CB_STATES.CLOSED;
    this._failureCount = 0;
    this._lastFailureTime = 0;
  }

  get state() {
    if (this._state === CB_STATES.OPEN) {
      // Check if cooldown has elapsed → transition to HALF_OPEN
      if (Date.now() - this._lastFailureTime >= this._cooldownMs) {
        this._state = CB_STATES.HALF_OPEN;
      }
    }
    return this._state;
  }

  /**
   * Execute an async function through the circuit breaker.
   * @param {() => Promise<any>} fn
   * @returns {Promise<any>}
   * @throws {Error} When breaker is OPEN (fast-fail)
   */
  async execute(fn) {
    const currentState = this.state; // triggers OPEN → HALF_OPEN check

    if (currentState === CB_STATES.OPEN) {
      throw new Error(
        `Circuit breaker is OPEN. Provider unavailable. Retry after ${Math.ceil(
          (this._cooldownMs - (Date.now() - this._lastFailureTime)) / 1000
        )}s.`
      );
    }

    try {
      const result = await fn();

      // Success: reset failure tracking
      this._failureCount = 0;
      this._state = CB_STATES.CLOSED;

      return result;
    } catch (error) {
      this._failureCount++;
      this._lastFailureTime = Date.now();

      if (this._failureCount >= this._failureThreshold) {
        this._state = CB_STATES.OPEN;
        console.error(
          `[CircuitBreaker] Opened after ${this._failureCount} consecutive failures.`
        );
      }

      throw error;
    }
  }

  /** Manually reset the breaker (e.g. after config change). */
  reset() {
    this._state = CB_STATES.CLOSED;
    this._failureCount = 0;
    this._lastFailureTime = 0;
  }
}

// ─── Shared Prompt ──────────────────────────────────────────────────

const STYLE_ANALYSIS_PROMPT = `
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

// ─── Provider Implementations ───────────────────────────────────────

/**
 * Call Ollama local API for image analysis.
 * @param {string} base64Data - Raw base64 image data (no data URI prefix)
 * @param {string} prompt
 * @param {object} opts - { url, model }
 * @returns {Promise<object>} Parsed filter object
 */
async function callOllama(base64Data, prompt, { url, model }) {
  const cleanUrl = url.replace(/\/$/, "");

  const ollamaRes = await fetch(`${cleanUrl}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: model,
      prompt: prompt,
      images: [base64Data],
      stream: false,
      format: "json",
    }),
  });

  if (!ollamaRes.ok) {
    throw new Error(
      `Ollama API error: ${ollamaRes.status} ${ollamaRes.statusText}`
    );
  }

  const ollamaData = await ollamaRes.json();
  const textOutput = ollamaData.response || "";

  try {
    return JSON.parse(textOutput);
  } catch (e) {
    console.error("Local model did not return pure JSON:", textOutput);
    throw new Error("Local model failed to generate valid JSON format.");
  }
}

/**
 * Call Gemini API for image analysis.
 * @param {string} base64Data - Raw base64 image data
 * @param {string} mimeType - e.g. "image/jpeg"
 * @param {string} prompt
 * @param {string} apiKey
 * @returns {Promise<object>} Parsed filter object
 */
async function callGemini(base64Data, mimeType, prompt, apiKey) {
  const ai = new GoogleGenAI({ apiKey });

  const response = await ai.models.generateContent({
    model: "gemini-1.5-flash",
    contents: [
      prompt,
      {
        inlineData: {
          data: base64Data,
          mimeType: mimeType,
        },
      },
    ],
  });

  const textOutput = response.text || "";
  const cleanJson = textOutput
    .replace(/```json/g, "")
    .replace(/```/g, "")
    .trim();

  try {
    return JSON.parse(cleanJson);
  } catch (err) {
    console.error("Failed to parse Gemini output:", cleanJson);
    throw new Error("Gemini failed to generate valid JSON format.");
  }
}

// ─── Default Filters ────────────────────────────────────────────────

const DEFAULT_FILTERS = Object.freeze({
  brightness: 100,
  contrast: 100,
  saturation: 100,
  sepia: 0,
  hueRotate: 0,
});

// ─── AI Engine Class ────────────────────────────────────────────────

export class AIEngine {
  constructor() {
    this._ollamaCB = new CircuitBreaker({
      failureThreshold: 3,
      cooldownMs: 30_000,
    });
    this._geminiCB = new CircuitBreaker({
      failureThreshold: 3,
      cooldownMs: 60_000,
    });
  }

  /**
   * Analyze an image's style and return CSS filter recommendations.
   *
   * Gemini Refinement #4: Response includes cbState so the UI can
   * display specific feedback ("Service Temporarily Unavailable"
   * vs generic "Analysis Failed") when the breaker is open.
   *
   * @param {string} base64Image - Full data URI (data:image/...;base64,...)
   * @param {object} options
   * @param {string} [options.provider="gemini"]
   * @param {string} [options.apiKey]
   * @param {string} [options.ollamaUrl="http://localhost:11434"]
   * @param {string} [options.ollamaModel="gemma4:e4b"]
   * @returns {Promise<{filters: object, provider: string, cbState: string}>}
   */
  async analyzeStyle(base64Image, options = {}) {
    const {
      provider = "gemini",
      apiKey,
      ollamaUrl = process.env.NEXT_PUBLIC_OLLAMA_URL || "http://localhost:11434",
      ollamaModel = "gemma4:e4b",
    } = options;

    // Parse data URI
    const match = base64Image.match(/^data:(image\/\w+);base64,(.*)$/);
    if (!match) {
      throw new Error("Invalid image format — expected data URI.");
    }
    const mimeType = match[1];
    const base64Data = match[2];

    let filters;
    let usedProvider = provider;
    let cbState;

    if (provider === "ollama") {
      cbState = this._ollamaCB.state;
      filters = await this._ollamaCB.execute(() =>
        callOllama(base64Data, STYLE_ANALYSIS_PROMPT, {
          url: ollamaUrl,
          model: ollamaModel,
        })
      );
      cbState = this._ollamaCB.state; // Post-execution state
    } else {
      // Gemini
      const keyToUse = apiKey || process.env.GEMINI_API_KEY;
      if (!keyToUse) {
        throw new Error("Gemini API key is required.");
      }

      cbState = this._geminiCB.state;
      filters = await this._geminiCB.execute(() =>
        callGemini(base64Data, mimeType, STYLE_ANALYSIS_PROMPT, keyToUse)
      );
      cbState = this._geminiCB.state; // Post-execution state
    }

    // Fallback sanity check
    if (!filters || typeof filters.brightness !== "number") {
      filters = { ...DEFAULT_FILTERS };
    }

    return {
      filters,
      provider: usedProvider,
      cbState,
    };
  }

  /**
   * Get current health status of all providers.
   * Gemini Refinement #4: Exposes CB state for UI toast rendering.
   *
   * @returns {{ ollama: string, gemini: string }}
   */
  getProviderHealth() {
    return {
      ollama: this._ollamaCB.state,
      gemini: this._geminiCB.state,
    };
  }

  /**
   * Manually reset a provider's circuit breaker.
   * @param {"ollama" | "gemini"} provider
   */
  resetProvider(provider) {
    if (provider === "ollama") this._ollamaCB.reset();
    else if (provider === "gemini") this._geminiCB.reset();
  }
}

// Singleton export for app-wide use
export const aiEngine = new AIEngine();
