"""Strands Decider 2B reading images: a photo check before an agent publishes a listing.

The decider reads the photo with the listing text (`images=`), so the check happens in one
forward pass, not an LLM call. Needs a vision decider: `./kit setup` with images on (local, v19
or the v1 Qwen3.5 release with --vision), or the AWS User Group Madurai hosted API.

    python -m examples.vision_check tests/data/red-square.png "Red square cushion, 40 cm"
"""

from __future__ import annotations

import sys

from strands import Agent, tool

from decider_kit import Decider
from decider_kit.llm import agent_model, strip_thinking

QUESTIONS = {
    "matches": Decider.noul("Does the photo show the item the listing text describes?",
                            {"true": "the photo shows that item (its kind, colour and shape agree with the text)",
                             "false": "the photo shows something else, or contradicts the text"}),
    "quality": Decider.score("How usable is the photo for a shop listing?",
                             ["unusable: blank, broken or unrelated", "poor: hard to see the item", "fine", "good: clear, the item fills the frame"]),
}


def check_photo(decider: Decider, text: str, photo: str) -> dict:
    a = decider.ask(f"Listing text: {text}", QUESTIONS, images=[photo])
    ok = a["matches"].p_yes >= 0.5 and a["quality"].label not in ("unusable: blank, broken or unrelated",)
    return {"matches": round(a["matches"].p_yes, 3), "quality": a["quality"].label, "publish": ok,
            "decider_ms": round(decider.last_latency_ms or 0)}


def main(photo: str, text: str) -> None:
    d = Decider()
    verdicts: list[dict] = []

    @tool
    def publish_listing(title: str) -> str:
        """Publish the listing with its photo to the shop."""
        v = check_photo(d, title, photo)
        verdicts.append(v)
        return "published" if v["publish"] else f"not published: the photo does not match ({v})"

    agent = Agent(model=agent_model(), tools=[publish_listing], callback_handler=None,
                  system_prompt="You publish shop listings. Call publish_listing with the title, then report the result in one sentence.")
    print(strip_thinking(str(agent(f"Publish this listing: {text}"))))
    print(verdicts)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tests/data/red-square.png",
         sys.argv[2] if len(sys.argv) > 2 else "Red square cushion, 40 cm")
