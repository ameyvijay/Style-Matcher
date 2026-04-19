"""
Antigravity Engine v2.1 — Module F.1: Prompt Registry
Versioned prompt templates for the VLM (Ollama/Moondream) inference pipeline.

Key Design:
- Manages versioned string templates for VLM prompts.
- Injects {few_shot_examples} and {genre_context} into a master template at runtime.
- Logs the exact prompt_version used per inference, enabling mathematical A/B
  optimisation of the AI Coach over time.

Usage:
    from prompt_registry import PromptRegistry
    registry = PromptRegistry()
    prompt = registry.get_prompt("v1.0", {"few_shot_examples": ..., "genre_context": ...})
"""
from __future__ import annotations

from typing import Dict, Optional


# ─── Versioned Templates ────────────────────────────────────────────
# Each key is a semantic version string.  Templates use Python str.format()
# placeholders: {few_shot_examples}, {genre_context}.  New versions are
# added below without touching existing entries — append-only.

_TEMPLATES: Dict[str, str] = {
    "v1.0": (
        "You are an expert photography critic analysing a photograph.\n"
        "\n"
        "## Genre Context\n"
        "{genre_context}\n"
        "\n"
        "## Accepted Exemplar Reference\n"
        "The photographer previously accepted the following similar images. "
        "Use them as a style benchmark when evaluating the current photo:\n"
        "{few_shot_examples}\n"
        "\n"
        "## Task\n"
        "Analyse the current image with the above context in mind. "
        "Describe the subject, lighting, mood, and composition. "
        "Compare it against the accepted exemplars — does it match the "
        "photographer's demonstrated style preferences? "
        "Be concise but precise (3-5 sentences)."
    ),
}

# Convenience constant: always points to the latest production version.
LATEST_VERSION = "v1.0"


class PromptRegistry:
    """
    Manages versioned VLM prompt templates.

    The registry is intentionally a thin, in-process lookup rather than
    a database table — prompt iteration speed matters more than
    persistence during active development.  The *version string* is what
    gets persisted alongside each inference for traceability.
    """

    def __init__(self):
        self._templates: Dict[str, str] = dict(_TEMPLATES)

    # ── Public API ──────────────────────────────────────────────────

    def get_prompt(
        self,
        version: str,
        context: dict,
    ) -> str:
        """
        Render a versioned prompt template with the supplied context.

        Args:
            version:  Semantic version key (e.g. "v1.0").
                      Falls back to LATEST_VERSION if not found.
            context:  Dict with optional keys:
                        - few_shot_examples (str): Formatted exemplar block.
                        - genre_context     (str): Genre description string.

        Returns:
            The fully rendered prompt string ready for VLM inference.
        """
        template = self._templates.get(version)
        if template is None:
            print(
                f"[prompt_registry] ⚠️  Version '{version}' not found; "
                f"falling back to '{LATEST_VERSION}'."
            )
            template = self._templates[LATEST_VERSION]
            version = LATEST_VERSION

        # Provide safe defaults so missing keys don't crash str.format()
        render_ctx = {
            "few_shot_examples": context.get(
                "few_shot_examples", "No prior exemplars available."
            ),
            "genre_context": context.get(
                "genre_context", "Genre not determined."
            ),
        }

        return template.format(**render_ctx)

    def register_version(self, version: str, template: str) -> None:
        """
        Hot-register a new prompt version at runtime (useful for notebook /
        A/B experimentation without restarting the engine).
        """
        if version in self._templates:
            print(
                f"[prompt_registry] ⚠️  Overwriting existing version '{version}'."
            )
        self._templates[version] = template
        print(f"[prompt_registry] Registered prompt version '{version}'.")

    @property
    def available_versions(self) -> list[str]:
        """Return all registered version keys."""
        return sorted(self._templates.keys())

    @property
    def latest_version(self) -> str:
        """Return the current production version string."""
        return LATEST_VERSION


# ─── Helper: Build context dict from RAG payload ─────────────────────

def build_prompt_context(rag_context: Optional[dict], genre: str = "general") -> dict:
    """
    Convert a SemanticRAG context payload into the dict expected by
    PromptRegistry.get_prompt().

    Args:
        rag_context:  Output of SemanticRAG.get_few_shot_context(), or None.
        genre:        Photography genre string (e.g. "portrait", "landscape").

    Returns:
        dict with 'few_shot_examples' and 'genre_context' keys.
    """
    from models import GENRE_PROFILES

    # Genre context
    profile = GENRE_PROFILES.get(genre, GENRE_PROFILES["general"])
    genre_text = (
        f"Genre: {profile['name']}. "
        f"Key weights — Sharpness: {profile['sharpness_weight']:.0%}, "
        f"Aesthetic: {profile['aesthetic_weight']:.0%}, "
        f"Exposure: {profile['exposure_weight']:.0%}."
    )

    # Few-shot exemplar block
    if rag_context and rag_context.get("exemplars"):
        exemplars = rag_context["exemplars"]
        lines = []
        for i, ex in enumerate(exemplars, 1):
            exif_str = ex.get("exif_snapshot") or "EXIF unavailable"
            lines.append(f"  Exemplar {i} (hash: {ex['photo_hash'][:12]}…): {exif_str}")
        sim = rag_context.get("similarity_score", 0.0)
        divergence = rag_context.get("divergence_warning", False)
        lines.append(f"  Aggregate similarity to accepted style: {sim:.1f}/100")
        if divergence:
            lines.append("  ⚠ Divergence warning: very high similarity — possible style collapse.")
        few_shot_text = "\n".join(lines)
    else:
        few_shot_text = "No prior exemplars available."

    return {
        "few_shot_examples": few_shot_text,
        "genre_context": genre_text,
    }


# ─── CLI Self-Test ───────────────────────────────────────────────────

if __name__ == "__main__":
    registry = PromptRegistry()
    print(f"Available versions: {registry.available_versions}")
    print(f"Latest: {registry.latest_version}")

    # Render a test prompt
    test_ctx = {
        "few_shot_examples": "  Exemplar 1 (hash: abc123): ISO 200, 50mm, f/2.8",
        "genre_context": "Genre: Portrait / Subject. Key weights — Sharpness: 40%, Aesthetic: 35%, Exposure: 25%.",
    }
    rendered = registry.get_prompt("v1.0", test_ctx)
    print("\n--- Rendered Prompt (v1.0) ---")
    print(rendered)
