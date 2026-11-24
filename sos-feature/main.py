from datetime import datetime
from uuid import uuid4

from flask import Flask, request, jsonify
from markupsafe import escape

app = Flask(__name__)

# In-memory store for this prototype (a database comes later in the project)
ALERTS = {}

EMERGENCY_TYPES = [
    ("not-sure", "Not sure"),
    ("medical", "Medical"),
    ("fire", "Fire"),
    ("accident", "Accident"),
    ("crime", "Crime / Police"),
    ("disaster", "Earthquake / Flood / Landslide"),
]

TYPE_LABELS = dict(EMERGENCY_TYPES)


def clean_location(value):
    """Return {lat, lng} if value is a valid location object, otherwise None."""
    if not isinstance(value, dict):
        return None
    lat = value.get("lat")
    lng = value.get("lng")
    if lat is None or lng is None:
        return None
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        return None
    return {"lat": lat, "lng": lng}


# ---------- Shared page pieces (used by every route) ----------

STYLE = """
<style>
  :root {
    --ink: #1c2430;
    --muted: #5d6877;
    --line: #d9dee5;
    --paper: #f6f8fa;
    --sos: #d62828;
    --sos-dark: #a61b1b;
    --ok: #1b7f4b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: var(--ink);
    background: var(--paper);
    line-height: 1.5;
  }
  header.top {
    display: flex; justify-content: space-between; align-items: center;
    padding: 14px 20px; background: #fff; border-bottom: 1px solid var(--line);
  }
  header.top .brand { font-weight: 700; font-size: 1.2rem; color: var(--ink); text-decoration: none; }
  header.top nav a { margin-left: 18px; color: var(--muted); text-decoration: none; }
  header.top nav a:hover, header.top nav a:focus { color: var(--ink); text-decoration: underline; }
  main { max-width: 760px; margin: 0 auto; padding: 28px 20px 120px; }
  h1 { font-size: 1.9rem; margin: 0 0 6px; }
  h2 { font-size: 1.15rem; margin: 28px 0 10px; }
  p.lead { color: var(--muted); margin: 0 0 24px; max-width: 60ch; }

  /* Emergency type picker */
  .types { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
  .types label {
    display: block; padding: 14px 12px; background: #fff; border: 2px solid var(--line);
    border-radius: 10px; cursor: pointer; font-weight: 600; text-align: center;
  }
  .types input { position: absolute; opacity: 0; }
  .types input:checked + span { color: var(--sos); }
  .types label:has(input:checked) { border-color: var(--sos); background: #fff1f1; }
  .types label:has(input:focus-visible) { outline: 3px solid #1c2430; outline-offset: 2px; }

  /* Big SOS button */
  .sos-wrap { text-align: center; margin: 34px 0 22px; }
  #sos-btn {
    width: 230px; height: 230px; border-radius: 50%; border: 0; cursor: pointer;
    background: var(--sos); color: #fff; font-size: 3.4rem; font-weight: 800; letter-spacing: 2px;
    box-shadow: 0 0 0 12px #fbd5d5, 0 8px 22px rgba(166, 27, 27, 0.35);
    transition: transform 0.1s, background 0.1s;
  }
  #sos-btn:hover { background: var(--sos-dark); }
  #sos-btn:active { transform: scale(0.96); }
  #sos-btn:focus-visible { outline: 4px solid #1c2430; outline-offset: 6px; }
  .sos-wrap small { display: block; margin-top: 18px; color: var(--muted); }

  /* Other ways to send */
  .modes { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
  .mode {
    background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 16px;
  }
  .mode h3 { margin: 0 0 4px; font-size: 1rem; }
  .mode p { margin: 0 0 12px; color: var(--muted); font-size: 0.92rem; }
  .btn {
    display: inline-block; padding: 10px 16px; border-radius: 8px; border: 2px solid var(--ink);
    background: #fff; color: var(--ink); font-weight: 600; font-size: 0.95rem; cursor: pointer; text-decoration: none;
  }
  .btn:hover { background: var(--ink); color: #fff; }
  .btn.listening { background: var(--sos); border-color: var(--sos); color: #fff; }
  #status { margin-top: 18px; min-height: 1.5em; color: var(--muted); }
  #status.error { color: var(--sos-dark); }

  /* Floating SOS button (every page except the main SOS page) */
  #float-sos {
    position: fixed; right: 18px; bottom: 18px; z-index: 50;
    width: 68px; height: 68px; border-radius: 50%; border: 0; cursor: pointer;
    background: var(--sos); color: #fff; font-weight: 800; font-size: 1.1rem;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
  }
  #float-sos:focus-visible { outline: 4px solid #1c2430; outline-offset: 3px; }

  /* Countdown overlay */
  #overlay {
    display: none; position: fixed; inset: 0; z-index: 100; background: rgba(28, 36, 48, 0.94);
    color: #fff; text-align: center; padding: 20vh 20px 0;
  }
  #overlay.show { display: block; }
  #count { font-size: 6rem; font-weight: 800; line-height: 1; }
  #overlay p { margin: 10px 0 24px; }
  #overlay .btn { margin: 0 6px; }

  table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid var(--line); }
  th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line); }
  .ok { color: var(--ok); font-weight: 700; }
  .ref { font-family: Consolas, monospace; background: #fff; border: 1px dashed var(--ink); padding: 4px 10px; border-radius: 6px; }

  @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
"""

# Countdown + send logic shared by the big button, voice, silent mode and the floating button
SHARED_JS = """
<div id="overlay" role="alertdialog" aria-live="assertive" aria-label="Sending SOS">
  <div id="count">3</div>
  <p>Sending SOS for <strong id="count-type">Not sure</strong>. Cancel if this was a mistake.</p>
  <button class="btn" id="send-now" style="background:#d62828;border-color:#d62828;color:#fff">Send now</button>
  <button class="btn" id="cancel" style="background:transparent;border-color:#fff;color:#fff">Cancel</button>
</div>
<script>
  var timer = null;

  function selectedType() {
    var checked = document.querySelector('input[name="etype"]:checked');
    return checked ? checked.value : "not-sure";
  }

  function setStatus(text, isError) {
    var box = document.getElementById("status");
    if (!box) return;
    box.textContent = text;
    box.className = isError ? "error" : "";
  }

  function getLocation() {
    return new Promise(function (resolve) {
      if (!navigator.geolocation) return resolve(null);
      navigator.geolocation.getCurrentPosition(
        function (pos) { resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }); },
        function () { resolve(null); },
        { timeout: 4000, enableHighAccuracy: true }
      );
    });
  }

  function sendSOS(etype, mode) {
    return getLocation().then(function (loc) {
      return fetch("/api/sos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: etype, mode: mode, location: loc })
      });
    }).then(function (res) { return res.json(); });
  }

  function finish(etype, mode) {
    sendSOS(etype, mode).then(function (data) {
      if (mode === "silent") {
        setStatus("Saved.", false);
      } else {
        window.location.href = "/sent/" + data.ref;
      }
    }).catch(function () {
      setStatus("Could not send. Call 100 (Police), 101 (Fire) or 102 (Ambulance) now.", true);
    });
  }

  function startCountdown(etype, mode) {
    var overlay = document.getElementById("overlay");
    var count = document.getElementById("count");
    document.getElementById("count-type").textContent = etype.replace("-", " ");
    var left = 3;
    count.textContent = left;
    overlay.classList.add("show");
    clearInterval(timer);
    timer = setInterval(function () {
      left -= 1;
      if (left <= 0) {
        clearInterval(timer);
        overlay.classList.remove("show");
        finish(etype, mode);
      } else {
        count.textContent = left;
      }
    }, 1000);
    document.getElementById("cancel").onclick = function () {
      clearInterval(timer);
      overlay.classList.remove("show");
      setStatus("SOS cancelled.", false);
    };
    document.getElementById("send-now").onclick = function () {
      clearInterval(timer);
      overlay.classList.remove("show");
      finish(etype, mode);
    };
  }
</script>
"""

FLOATING_SOS = """
<button id="float-sos" aria-label="Send SOS">SOS</button>
<script>
  document.getElementById("float-sos").onclick = function () { startCountdown("not-sure", "tap"); };
</script>
"""

NAV = """
<header class="top">
  <a class="brand" href="/">ResponZa</a>
  <nav>
    <a href="/">SOS</a>
    <a href="/about">How it works</a>
    <a href="/contact">Emergency numbers</a>
  </nav>
</header>
"""


def page(title, body, floating=True):
    """Wrap a page body with the shared style, navigation and floating SOS button."""
    html = "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
    html += "<meta name='viewport' content='width=device-width, initial-scale=1'>"
    html += "<title>" + title + " | ResponZa</title>" + STYLE + "</head><body>"
    html += NAV + "<main>" + body + "</main>" + SHARED_JS
    if floating:
        html += FLOATING_SOS
    html += "</body></html>"
    return html


# ---------- Routes ----------

@app.route("/")
def home():
    picker = ""
    for value, label in EMERGENCY_TYPES:
        checked = " checked" if value == "not-sure" else ""
        picker += (
            "<label><input type='radio' name='etype' value='" + value + "'" + checked + ">"
            "<span>" + label + "</span></label>"
        )

    body = """
        <h1>Send an SOS</h1>
        <p class="lead">Choose the type of emergency, then press the SOS button.
        Your location is shared with the alert so responders can find you.</p>

        <h2 id="pick">1. What is the emergency?</h2>
        <div class="types" role="radiogroup" aria-labelledby="pick">__PICKER__</div>

        <h2>2. Press SOS</h2>
        <div class="sos-wrap">
            <button id="sos-btn" aria-label="Send SOS">SOS</button>
            <small>You get 3 seconds to cancel after you press.</small>
        </div>

        <h2>Other ways to send</h2>
        <div class="modes">
            <div class="mode">
                <h3>By voice</h3>
                <p>Turn this on, then say "help", "SOS" or "emergency".</p>
                <button class="btn" id="voice-btn">Start voice SOS</button>
            </div>
            <div class="mode">
                <h3>Silent</h3>
                <p>Sends right away with no countdown and no sound. Use it when speaking is unsafe.</p>
                <button class="btn" id="silent-btn">Send silent SOS</button>
            </div>
        </div>

        <div id="status" role="status" aria-live="polite"></div>

        <script>
            document.getElementById("sos-btn").onclick = function () {
                startCountdown(selectedType(), "tap");
            };

            document.getElementById("silent-btn").onclick = function () {
                finish(selectedType(), "silent");
            };

            var recognition = null;
            var listening = false;
            var voiceBtn = document.getElementById("voice-btn");
            var triggerWords = ["help", "sos", "emergency", "bachau", "madat"];

            voiceBtn.onclick = function () {
                var Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
                if (!Speech) {
                    setStatus("Voice SOS is not supported in this browser. Try Chrome, or use the SOS button.", true);
                    return;
                }
                if (listening) {
                    recognition.stop();
                    return;
                }
                recognition = new Speech();
                recognition.lang = "en-US";
                recognition.continuous = true;
                recognition.interimResults = true;

                recognition.onstart = function () {
                    listening = true;
                    voiceBtn.textContent = "Listening... tap to stop";
                    voiceBtn.classList.add("listening");
                    setStatus("Listening for a trigger word.", false);
                };
                recognition.onresult = function (event) {
                    var heard = "";
                    for (var i = event.resultIndex; i < event.results.length; i++) {
                        heard += event.results[i][0].transcript.toLowerCase() + " ";
                    }
                    for (var j = 0; j < triggerWords.length; j++) {
                        if (heard.indexOf(triggerWords[j]) !== -1) {
                            recognition.stop();
                            startCountdown(selectedType(), "voice");
                            return;
                        }
                    }
                };
                recognition.onerror = function () {
                    setStatus("Microphone access failed. Allow the microphone, or use the SOS button.", true);
                };
                recognition.onend = function () {
                    listening = false;
                    voiceBtn.textContent = "Start voice SOS";
                    voiceBtn.classList.remove("listening");
                };
                recognition.start();
            };
        </script>
    """.replace("__PICKER__", picker)

    # The main SOS page already has the big button, so no floating button here
    return page("Send an SOS", body, floating=False)


@app.route("/sent/<ref>")
def sent(ref):
    alert = ALERTS.get(ref)
    if alert is None:
        return page(
            "Not found",
            """
            <h1>Alert not found</h1>
            <p class="lead">This reference does not exist. If you need help now, call 100, 101 or 102.</p>
            <a class="btn" href="/">Back to SOS</a>
            """,
        ), 404

    if isinstance(alert.get("location"), dict):
        where = "%.5f, %.5f" % (
            alert["location"]["lat"],
            alert["location"]["lng"],
        )
    else:
        where = "Not shared (location permission was off)"

    return page(
        "SOS sent",
        f"""
        <h1 class="ok">SOS sent</h1>
        <p class="lead">Your alert is saved. Stay where it is safe and keep your phone with you.</p>
        <table>
            <tr><th>Reference</th><td><span class="ref">{escape(ref)}</span></td></tr>
            <tr><th>Emergency type</th><td>{escape(TYPE_LABELS.get(alert["type"], "Not sure"))}</td></tr>
            <tr><th>Sent by</th><td>{escape(str(alert["mode"])).capitalize()}</td></tr>
            <tr><th>Location</th><td>{escape(where)}</td></tr>
            <tr><th>Time</th><td>{escape(alert["time"])}</td></tr>
        </table>
        <p style="margin-top:20px"><a class="btn" href="/">Send another SOS</a></p>
        """,
    )


@app.route("/api/sos", methods=["POST"])
def api_sos():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}

    etype = data.get("type", "not-sure")
    if etype not in TYPE_LABELS:
        etype = "not-sure"

    mode = data.get("mode", "tap")
    if mode not in ("tap", "voice", "silent"):
        mode = "tap"

    location = clean_location(data.get("location"))

    ref = uuid4().hex[:8].upper()
    ALERTS[ref] = {
        "type": etype,
        "mode": mode,
        "location": location,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return jsonify({"ref": ref, "status": "received"})


@app.route("/about")
def about():
    return page("How it works", """
        <h1>How SOS works</h1>
        <p class="lead">There are three ways to send an alert. All of them share your location
        and the emergency type you picked.</p>
        <h2>Tap</h2>
        <p>Pick the emergency type and press the big SOS button. You have 3 seconds to cancel.</p>
        <h2>Voice</h2>
        <p>Turn on voice SOS and say "help", "SOS" or "emergency". The same 3-second countdown applies.</p>
        <h2>Silent</h2>
        <p>Sends immediately with no countdown and no sound, for situations where you cannot speak or be noticed.</p>
        <h2>Floating SOS button</h2>
        <p>The red SOS button in the corner of every page sends a general alert, so help is one press away
        wherever you are on the site.</p>
        <p><a class="btn" href="/">Go to SOS</a></p>
    """)


@app.route("/contact")
def contact():
    return page("Emergency numbers", """
        <h1>Emergency numbers in Nepal</h1>
        <p class="lead">If the SOS does not go through, call directly.</p>
        <table>
            <tr><th>Police</th><td>100</td></tr>
            <tr><th>Fire brigade</th><td>101</td></tr>
            <tr><th>Ambulance</th><td>102</td></tr>
        </table>
        <p style="margin-top:20px"><a class="btn" href="/">Back to SOS</a></p>
    """)


@app.route("/alerts")
def alerts():
    # Simple list of everything received so far, handy for testing during development
    rows = ""
    for ref, a in reversed(list(ALERTS.items())):
        rows += (
            "<tr><td>" + escape(ref) + "</td><td>"
            + escape(TYPE_LABELS.get(a["type"], "Not sure")) + "</td><td>"
            + escape(str(a["mode"])) + "</td><td>"
            + escape(a["time"]) + "</td></tr>"
        )
    if not rows:
        rows = "<tr><td colspan='4'>No alerts yet.</td></tr>"
    return page("Received alerts", """
        <h1>Received alerts</h1>
        <p class="lead">Test view for developers. This list resets when the server restarts.</p>
        <table>
            <tr><th>Reference</th><th>Type</th><th>Sent by</th><th>Time</th></tr>
            """ + rows + """
        </table>
    """)


@app.errorhandler(404)
def not_found(e):
    return page(
        "Page not found",
        """
        <h1>Page not found</h1>
        <p class="lead">That page doesn't exist. If you need help now, call 100, 101 or 102.</p>
        <a class="btn" href="/">Back to SOS</a>
        """,
    ), 404


@app.errorhandler(500)
def server_error(e):
    return page(
        "Server error",
        """
        <h1>Server error</h1>
        <p class="lead">Something went wrong on our end. Try again, or if you need help now, call 100, 101 or 102.</p>
        <a class="btn" href="/">Back to SOS</a>
        """,
    ), 500


if __name__ == "__main__":
    # debug=True is for local development only; turn it off for production.
    app.run(debug=True)
