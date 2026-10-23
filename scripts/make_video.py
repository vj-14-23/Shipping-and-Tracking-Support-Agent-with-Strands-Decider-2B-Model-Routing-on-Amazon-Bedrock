"""Make the demo video (under 3 minutes) from a real run of your agent.

    ./kit video          # or: python scripts/make_video.py [--target agentcore]

1. Starts the demo UI (unless one is already running) and records it with Playwright while it
   plays the turns in agent/demo_script.yaml against your real agent.
2. Writes narration for each part from the script and from what actually happened (the decider's
   numbers and verdicts), and speaks it with Amazon Polly (falls back to macOS `say`).
3. Adds a title card, a benchmark slide (from `./kit bench`) and an end card (tags, repo, credits).
4. Assembles an MP4 with ffmpeg (bundled through imageio-ffmpeg), checks it is under 2:55, and
   writes submission/video/demo.mp4 plus the narration script.

Upload the MP4 to YouTube or Vimeo yourself (public or unlisted-public) and paste the link into
submission/SUBMISSION.md: the rules require a public video link.
"""

from __future__ import annotations

import argparse
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "submission" / "video"
W, H = 1280, 720
MAX_S = 170.0


def ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def duration(path: Path) -> float:
    r = subprocess.run([ffmpeg(), "-i", str(path)], stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


# ---- narration -----------------------------------------------------------------------------------


def tts(text: str, out: Path) -> Path:
    """Speech for `text` as an mp3: Amazon Polly (neural) if AWS works, else macOS `say`."""
    try:
        import boto3

        from decider_kit.config import settings

        polly = boto3.client("polly", region_name=settings().aws_region)
        r = polly.synthesize_speech(Text=text, OutputFormat="mp3", VoiceId=os.environ.get("POLLY_VOICE", "Matthew"),
                                    Engine="neural")
        out.write_bytes(r["AudioStream"].read())
        return out
    except Exception as e:  # noqa: BLE001
        if shutil.which("say"):
            aiff = out.with_suffix(".aiff")
            subprocess.run(["say", "-r", "185", "-o", str(aiff), text], check=True)
            run([ffmpeg(), "-y", "-i", str(aiff), str(out)])
            return out
        raise RuntimeError(f"no text-to-speech available (Polly failed: {e}; no `say`)") from e


def facts_for(turn_out: dict) -> str:
    """One sentence on what the decider actually decided in this turn."""
    ds = turn_out.get("decisions") or []
    if not ds:
        return "No decision was needed on this turn."
    parts = []
    for d in ds[:2]:
        nums = [f"{k.replace('_', ' ')} {v:.2f}" for k, v in d.items() if isinstance(v, float) and 0 <= v <= 1][:3]
        verdict = d.get("verdict") or d.get("action") or d.get("tier") or "decided"
        ms = d.get("decider_ms")
        parts.append(f"The decider scored {', '.join(nums)}, so the verdict was {verdict}" + (f", in {ms / 1000:.1f} seconds" if ms else ""))
    return ". ".join(parts) + "."


# ---- slides --------------------------------------------------------------------------------------

SLIDE_CSS = """body{margin:0;width:1280px;height:720px;background:#0B1020;color:#E7ECF6;font-family:Inter,Helvetica,Arial,sans-serif;
display:flex;flex-direction:column;justify-content:center;padding:70px;box-sizing:border-box}
h1{font-size:54px;margin:0 0 18px;letter-spacing:-.02em} h1 b{color:#FF9900} p{font-size:26px;color:#A9B4C9;margin:8px 0;line-height:1.35}
.tag{display:inline-block;border:1px solid #FF9900;color:#FFB547;border-radius:99px;padding:6px 16px;font-size:22px;margin:16px 10px 0 0}
.credit{position:absolute;bottom:40px;left:70px;font-size:20px;color:#8D9AB5} img{max-width:1140px;max-height:470px;border-radius:12px;background:#fff}"""


def slide(html: str, out: Path) -> Path:
    from playwright.sync_api import sync_playwright

    page = out.with_suffix(".html")
    page.write_text(f"<!doctype html><html><head><meta charset='utf-8'><style>{SLIDE_CSS}</style></head><body>{html}</body></html>")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(page.as_uri())
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(out))
        b.close()
    return out


def still_clip(image: Path, audio: Path, out: Path, pad: float = 0.8) -> Path:
    d = duration(audio) + pad
    run([ffmpeg(), "-y", "-loop", "1", "-i", str(image), "-i", str(audio), "-t", f"{d:.2f}", "-vf", f"scale={W}:{H},format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-r", "30", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-af", "apad", str(out)])
    return out


def segment_clip(rec: Path, start: float, end: float, audio: Path, out: Path) -> Path:
    """The recording between start and end, fitted to the narration: frozen at the end if the
    narration is longer, sped up (up to 2.5x) if the recording is longer."""
    seg = max(0.5, end - start)
    speech = duration(audio) + 0.6
    speed = min(2.5, seg / speech) if seg > speech else 1.0
    vlen = seg / speed
    pad = max(0.0, speech - vlen)
    vf = f"trim=start={start:.2f}:end={end:.2f},setpts=(PTS-STARTPTS)/{speed:.3f},scale={W}:{H},tpad=stop_mode=clone:stop_duration={pad:.2f},format=yuv420p"
    run([ffmpeg(), "-y", "-i", str(rec), "-i", str(audio), "-filter_complex", f"[0:v]{vf}[v];[1:a]apad[a]", "-map", "[v]", "-map", "[a]",
         "-t", f"{max(vlen, speech):.2f}", "-c:v", "libx264", "-preset", "veryfast", "-r", "30", "-c:a", "aac", "-ar", "44100", "-ac", "2", str(out)])
    return out


# ---- recording -----------------------------------------------------------------------------------


def ensure_demo(port: int, target: str, eager: bool = False) -> subprocess.Popen | None:
    url = f"http://127.0.0.1:{port}/api/info"
    try:
        urllib.request.urlopen(url, timeout=2)
        print(f"[video] using the demo UI already running on port {port} (start it with DEMO_EAGER={int(eager)} to match the script)")
        return None
    except Exception:  # noqa: BLE001
        pass
    env = {**os.environ, **({"DEMO_TARGET": "agentcore"} if target == "agentcore" else {}), "DEMO_EAGER": "1" if eager else "0"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "demo.server:app", "--port", str(port)], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            urllib.request.urlopen(url, timeout=2)
            return proc
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise RuntimeError("the demo UI did not start (try `./kit demo` and read its output)")


def record(script: dict, port: int, workdir: Path) -> tuple[Path, list[dict]]:
    from playwright.sync_api import sync_playwright

    marks = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(workdir), record_video_size={"width": W, "height": H})
        pg = ctx.new_page()
        t0 = time.time()
        pg.goto(f"http://127.0.0.1:{port}/")
        pg.wait_for_timeout(1500)
        for i, turn in enumerate(script["turns"]):
            start = time.time() - t0
            imgs = turn.get("image") or turn.get("images") or []
            if imgs:  # attach the photo(s) with the paperclip, as a user would
                pg.set_input_files("#img", [str(ROOT / x) for x in ([imgs] if isinstance(imgs, str) else imgs)])
                pg.wait_for_timeout(900)
            with pg.expect_response(lambda r: "/api/chat" in r.url, timeout=180_000) as resp:
                pg.fill("#m", "")
                pg.type("#m", turn["say"], delay=28)
                pg.press("#m", "Enter")
            out = resp.value.json()
            pg.wait_for_function(f"document.body.dataset.turns >= {i + 1}", timeout=30_000)
            pg.wait_for_timeout(1800)
            marks.append({"start": start, "end": time.time() - t0, "out": out, **turn})
        pg.wait_for_timeout(800)
        video = pg.video.path()
        ctx.close()
        b.close()
    return Path(video), marks


# ---- main ------------------------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=os.environ.get("DEMO_TARGET", "local"), choices=["local", "agentcore"])
    ap.add_argument("--port", type=int, default=8501)
    ap.add_argument("--repo", default=os.environ.get("REPO_URL", ""))
    a = ap.parse_args()
    import yaml

    from decider_kit.config import load_dotenv, settings

    load_dotenv()
    script = yaml.safe_load((ROOT / "agent" / "demo_script.yaml").read_text(encoding="utf-8"))
    tag = "#guardrails"
    try:
        from agent import decision

        tag = getattr(decision, "PATTERN_TAG", tag)
    except Exception:  # noqa: BLE001
        pass
    OUT.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="decider-video-"))
    proc = ensure_demo(a.port, a.target, bool(script.get("eager")))
    try:
        print("[video] recording the demo against your real agent...")
        rec, marks = record(script, a.port, work)
    finally:
        if proc:
            proc.terminate()
    s = settings()
    clips, narration = [], []

    title = script.get("title", "My Strands Decider agent")
    intro = script.get("intro", "")
    # Free-text lines carry no numbers: figures come only from the run and the benchmark
    for key in ("intro", "intro_normal", "outro", "pitch"):
        if re.search(r"\d", str(script.get(key) or "")):
            sys.exit(f"[video] demo_script.yaml '{key}' contains a number: say it without figures; the video adds the "
                     "measured numbers itself (decisions per turn and the benchmark slide)")
    for t in script.get("turns", []):
        if re.search(r"\d+(\.\d+)?\s*(s|ms|seconds|%|percent)\b", str(t.get("narrate", ""))):
            sys.exit("[video] a turn's narrate line states a measurement; describe the situation only")
    if a.target == "agentcore" and script.get("eager"):
        dep = ROOT / "submission" / "deployment.json"
        deployed_eager = dep.exists() and json.loads(dep.read_text()).get("eager", False)
        if not deployed_eager:  # the deployed agent is not in demo-eager mode: say what is true
            intro = script.get("intro_normal") or intro
            print("[video] the deployed agent is not eager; using intro_normal from demo_script.yaml")
    from decider_kit.llm import describe

    llm_where = f"Amazon Bedrock ({s.bedrock_model})" if a.target == "agentcore" else describe()
    t_img = slide(f"<h1>{title}</h1><p>{llm_where} for the conversation.</p>"
                  f"<p><b style='color:#FF9900'>Strands Decider 2B</b> for the decision.</p>"
                  f"<div><span class='tag'>#strands-decider-2b</span><span class='tag'>{tag}</span></div>"
                  "<div class='credit'>Built with the AWS User Group Madurai Strands Decider hackathon kit</div>", work / "title.png")
    narration.append(intro)
    clips.append(still_clip(t_img, tts(intro, work / "n0.mp3"), work / "c0.mp4"))
    feats = script.get("features") or []
    if feats:  # the project itself, before the decision: what it is and what it can do
        pitch = script.get("pitch", "")
        # features may be phrases ("search live listings") or sentences: list them, never glue them into one
        items = [f.strip().rstrip(".")[:1].upper() + f.strip().rstrip(".")[1:] for f in feats[:4]]
        txt = (pitch.rstrip(".") + ". " if pitch else "") + "What it does: " + ". ".join(items) + "."
        narration.append(txt)
        f_img = slide(f"<h1>{title}</h1>" + (f"<p>{pitch}</p>" if pitch else "") +
                      "".join(f"<p>&#8226; {x}</p>" for x in feats[:5]), work / "features.png")
        clips.append(still_clip(f_img, tts(txt, work / "nf.mp3"), work / "cf.mp4"))
    if a.target == "agentcore":
        arn = os.environ.get("AGENTCORE_ARN", "")
        txt = "The agent you are about to see is running on Amazon Bedrock AgentCore Runtime."
        narration.append(txt)
        on_aws = slide(f"<h1>Running on <b>AWS</b></h1><p>Amazon Bedrock AgentCore Runtime</p><p style='font-size:18px'>{arn}</p>", work / "aws.png")
        clips.append(still_clip(on_aws, tts(txt, work / "naws.mp3"), work / "caws.mp4"))
    for i, m in enumerate(marks, 1):
        text = f"{m.get('narrate', '')} {facts_for(m['out'])}".strip()
        narration.append(text)
        clips.append(segment_clip(rec, m["start"], m["end"], tts(text, work / f"n{i}.mp3"), work / f"c{i}.mp4"))
    bench = ROOT / "submission" / "bench" / "results.json"
    if bench.exists():
        full = json.loads(bench.read_text())
        r = full["summary"]
        dsum, lsum = r["decider"], r.get("llm")
        where = {"local": "running locally on this machine", "ugmdu": "on the AWS User Group Madurai hosted API",
                 "custom": "on a hosted endpoint"}.get(full.get("decider_mode", ""), "")
        txt = (f"On {dsum['decisions']} labelled decisions, with the decider {where}, Strands Decider was "
               f"{dsum['accuracy']:.0%} accurate at a median of {dsum['latency_p50_ms']:.0f} milliseconds")
        if lsum:
            who = {"bedrock": "the Bedrock LLM", "local": "a local LLM", "ugmdu": "a hosted open LLM"}.get(full.get("llm_provider", "bedrock"), "the LLM")
            txt += f", against {lsum['accuracy']:.0%} and {lsum['latency_p50_ms']:.0f} milliseconds for {who} asked the same questions"
        txt += "."
        img = ROOT / "submission" / "bench" / "bench-latency.png"
        b_img = slide(f"<h1>Measured</h1><img src='{img.as_uri()}'>", work / "bench.png")
        narration.append(txt)
        clips.append(still_clip(b_img, tts(txt, work / "nb.mp3"), work / "cb.mp4"))
    outro = script.get("outro", "")
    e_img = slide(f"<h1>{title}</h1><p>Code and the reusable decision pattern: {a.repo or 'see the article'}</p>"
                  f"<div><span class='tag'>#strands-decider-2b</span><span class='tag'>{tag}</span></div>"
                  "<div class='credit'>Built with the AWS User Group Madurai Strands Decider hackathon kit · awsugmdu.in</div>", work / "end.png")
    narration.append(outro)
    clips.append(still_clip(e_img, tts(outro or "Thanks for watching.", work / "ne.mp3"), work / "ce.mp4"))

    lst = work / "list.txt"
    lst.write_text("".join(f"file '{c}'\n" for c in clips))
    out = OUT / "demo.mp4"
    run([ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         "-c:a", "aac", "-movflags", "+faststart", str(out)])
    total = duration(out)
    if total > MAX_S:  # speed the whole thing up a little rather than break the 3-minute rule
        f = total / MAX_S
        tmp = OUT / "demo_fast.mp4"
        run([ffmpeg(), "-y", "-i", str(out), "-filter_complex", f"[0:v]setpts=PTS/{f:.4f}[v];[0:a]atempo={f:.4f}[a]",
             "-map", "[v]", "-map", "[a]", str(tmp)])
        tmp.replace(out)
        total = duration(out)
    (OUT / "narration.md").write_text("\n\n".join(f"{i}. {t}" for i, t in enumerate(narration)))
    (OUT / "run.json").write_text(json.dumps([{k: v for k, v in m.items()} for m in marks], indent=1, default=str))
    shutil.copy(rec, OUT / "raw-recording.webm")
    sys.path.insert(0, str(ROOT / "scripts"))
    from publish import submission_md

    submission_md()  # creates submission/SUBMISSION.md if needed, keeping any links already in it
    print(f"[video] {out} ({total:.0f} s). Upload it to YouTube or Vimeo as public, then put the link in submission/SUBMISSION.md")


if __name__ == "__main__":
    main()
