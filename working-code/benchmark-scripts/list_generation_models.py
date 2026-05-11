"""Probe: list every model the current API key can see, marking generateContent support.

Throwaway diagnostic. Used to discover candidate models for the vision-perception A/B
against gemini-3.1-pro-preview. Safe to delete after the right model is locked in.
"""

from google import genai


def main() -> None:
    client = genai.Client()
    print("All models visible to this API key (marked GEN if generateContent supported):\n")
    for m in client.models.list():
        actions = list(getattr(m, "supported_actions", []) or [])
        gen = any("generatecontent" in a.lower().replace("_", "") for a in actions)
        marker = "  [GEN]" if gen else ""
        print(f"- {m.name}{marker}")
        if actions:
            print(f"    actions: {actions}")


if __name__ == "__main__":
    main()
