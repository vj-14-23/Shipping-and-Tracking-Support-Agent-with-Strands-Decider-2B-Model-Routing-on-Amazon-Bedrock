"""Amazon Bedrock AgentCore Runtime entry point for the hackathon agent.

`make deploy` copies agent/ and decider_kit/ next to this file. The runtime gets DECIDER_MODE,
DECIDER_URL, DECIDER_API_KEY and BEDROCK_MODEL_ID as environment variables.

Payload: {"prompt": "...", "session_id": "optional", "images": ["<base64>", ...] (optional)}
    ->  the HackathonAgent.chat() result as JSON.
"""

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from agent.agent import HackathonAgent

app = BedrockAgentCoreApp()
_agent = HackathonAgent()


@app.entrypoint
def invoke(payload, context):
    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    if not isinstance(prompt, str) or not prompt.strip():
        return {"error": "send {\"prompt\": \"...\"}"}
    session = payload.get("session_id") or getattr(context, "session_id", None) or "default"
    images = payload.get("images") if isinstance(payload, dict) else None
    out = _agent.chat(prompt, session, images=images) if images else _agent.chat(prompt, session)
    out["served_by"] = "Amazon Bedrock AgentCore Runtime"
    return out


if __name__ == "__main__":
    app.run()
