import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from decider_kit.client import Decider, DeciderError, Decision


def test_parse_types():
    n = Decision.parse({"type": "noul", "noul": 0.2})
    assert n.p_yes == 0.2 and not n.yes and n.label == "no" and n.confidence == pytest.approx(0.8)
    c = Decision.parse({"type": "choice", "choice": "a", "probabilities": {"a": 0.7, "b": 0.3}})
    assert c.label == "a" and c.confidence == 0.7 and not c.unsure(0.6) and c.unsure(0.8)
    s = Decision.parse({"type": "score", "score": 1.4, "probabilities": {"0": 0.1, "1": 0.5, "2": 0.4}, "legend": {"0": "low", "1": "mid", "2": "high"}})
    assert s.label == "mid" and s.probabilities["high"] == 0.4


class _H(BaseHTTPRequestHandler):
    seen: list = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        _H.seen.append((self.path, self.headers.get("authorization"), body))
        ans = {k: {"type": "noul", "noul": 0.9} for k in body["questions"]}
        out = json.dumps({"answers": ans, "usage": {"input_tokens": 42}, "latency_ms": 5.0}).encode()
        self.send_response(401 if self.headers.get("authorization") == "Bearer bad" else 200)
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


@pytest.fixture()
def server():
    s = HTTPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}"
    s.shutdown()


def test_local_and_hosted_wire(server, monkeypatch):
    monkeypatch.setenv("DECIDER_MODE", "local")
    d = Decider(url=server, api_key="")
    a = d.ask("s", {"q": Decider.noul("ok?")})
    assert a["q"].yes and _H.seen[-1][0] == "/v1/systemone" and d.input_tokens == 42 and d.last_server_ms == 5.0
    h = Decider(url=server, api_key="k1")
    h.ask("s", {"q": Decider.noul("ok?")})
    assert _H.seen[-1][0] == "/v1/decide" and _H.seen[-1][1] == "Bearer k1"
    with pytest.raises(DeciderError, match="401"):
        Decider(url=server, api_key="bad").ask("s", {"q": Decider.noul("ok?")})


def test_unreachable_message():
    with pytest.raises(DeciderError, match="./kit serve"):
        Decider(url="http://127.0.0.1:1", api_key="", timeout=1).ask("s", {"q": Decider.noul("x")})
