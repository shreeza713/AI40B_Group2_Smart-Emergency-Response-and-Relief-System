from datetime import datetime
from uuid import uuid4

from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# In-memory store for this prototype (a database comes later in the project)
ALERTS = {}

# Emergency types, plus "Not sure" so nobody is blocked in a hurry
EMERGENCY_TYPES = [
    ("medical", "Medical"),
    ("fire", "Fire"),
    ("accident", "Accident"),
    ("crime", "Crime / Police"),
    ("disaster", "Earthquake / Flood"),
    ("not-sure", "Not sure"),
]
TYPE_LABELS = dict(EMERGENCY_TYPES)

# Words that start a voice SOS
TRIGGER_WORDS = ["help", "sos", "emergency", "bachau", "madat"]

# Without JavaScript the browser cannot read GPS, so the pinned location is set here.
# Every method (tap, voice, silent) sends this same location.
# Later the real GPS reading from the mobile app replaces these values.
DEFAULT_LOCATION = {
    "place": "Jhamsikhel, Ward 3",
    "lat": 27.6710,
    "lng": 85.3070,
}


def heard_trigger(command):
    """True if the typed voice command contains one of the trigger words."""
    text = command.lower()
    for word in TRIGGER_WORDS:
        if word in text:
            return True
    return False


def make_summary(alert):
    """Text summary created from a voice command."""
    return (
        "Voice SOS for " + alert["type_label"] + ". "
        + 'Heard: "' + alert["command"] + '". '
        + "Location: " + alert["place"] + " (%.4f N, %.4f E). " % (alert["lat"], alert["lng"])
        + "Time: " + alert["time"] + "."
    )


@app.route("/")
def home():
    # Only the Report section is built so far, so the home page opens it
    return redirect(url_for("report"))


# ---------- Sidebar pages (empty templates, other developers fill them in) ----------

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", active="dashboard")


@app.route("/map")
def map_page():
    return render_template("map.html", active="map")


@app.route("/incidents")
def incidents():
    return render_template("incidents.html", active="incidents")


@app.route("/alerts")
def alerts():
    return render_template("alerts.html", active="alerts")


@app.route("/admin")
def admin():
    return render_template("admin.html", active="admin")


@app.route("/security")
def security():
    return render_template("security.html", active="security")


# ---------- Report section (hub page) ----------
# Each feature of the Report section gets its own card in templates/report.html
# and its own routes below, so developers do not touch each other's code.

@app.route("/report")
def report():
    return render_template("report.html", active="report")


# ---------- Feature 1.1: SOS by tap, voice or silent ----------

@app.route("/report/sos", methods=["GET", "POST"])
def sos():
    error = None
    selected = "not-sure"
    command = ""

    if request.method == "POST":
        selected = request.form.get("etype", "not-sure")
        if selected not in TYPE_LABELS:
            selected = "not-sure"

        mode = request.form.get("mode", "tap")
        if mode not in ("tap", "voice", "silent"):
            mode = "tap"

        command = request.form.get("command", "").strip()

        if mode == "voice" and not heard_trigger(command):
            error = 'No trigger word heard. Say or type "help", "SOS" or "emergency" in the voice box.'
        else:
            ref = uuid4().hex[:8].upper()
            alert = {
                "ref": ref,
                "type_label": TYPE_LABELS[selected],
                "mode": mode,
                "place": DEFAULT_LOCATION["place"],
                "lat": DEFAULT_LOCATION["lat"],
                "lng": DEFAULT_LOCATION["lng"],
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "command": command,
                "summary": None,
            }
            if mode == "voice":
                alert["summary"] = make_summary(alert)
            ALERTS[ref] = alert
            return redirect(url_for("sos_sent", ref=ref))

    return render_template(
        "sos.html",
        active="report",
        types=EMERGENCY_TYPES,
        selected=selected,
        command=command,
        error=error,
        loc=DEFAULT_LOCATION,
    )


@app.route("/report/sos/sent/<ref>")
def sos_sent(ref):
    alert = ALERTS.get(ref)
    status = 200 if alert else 404
    return render_template(
        "sos_sent.html", active="report", alert=alert, loc=DEFAULT_LOCATION
    ), status


if __name__ == "__main__":
    app.run(debug=True)
