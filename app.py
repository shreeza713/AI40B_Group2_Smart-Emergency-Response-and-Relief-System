from datetime import datetime
from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)

ENCRYPTED_CHANNELS = [
    {
        "title": "Live GPS & location logs",
        "detail": "Encrypted in transit and at rest · Active case access only",
        "badge": "Encrypted",
    },
    {
        "title": "Incident reports & messages",
        "detail": "Encrypted emergency submissions and responder threads",
        "badge": "Encrypted",
    },
    {
        "title": "Data protection compliance",
        "detail": "Purpose-limited processing & retention controls active",
        "badge": "Compliant",
    },
]

CONSENTS = [
    {
        "key": "hospitals",
        "title": "Partner hospitals & triage",
        "detail": "Requires explicit opt-in before sharing case details",
        "enabled": False,
    },
    {
        "key": "relief",
        "title": "Verified relief & shelter teams",
        "detail": "Requires explicit opt-in for aid coordination",
        "enabled": False,
    },
    {
        "key": "research",
        "title": "Anonymized disaster summaries",
        "detail": "Requires explicit opt-in for de-identified reporting",
        "enabled": False,
    },
]

DELETION_REQUEST = {
    "requested": False,
    "reason": None,
    "updated_at": None,
}

LAST_MESSAGE = None
LAST_ERROR = None


def get_initials(full_name):
    parts = [p[0].upper() for p in full_name.split() if p]
    return "".join(parts[:2]) or "MR"


@app.route("/")
@app.route("/security")
def home():
    global LAST_MESSAGE, LAST_ERROR
    show_policy = request.args.get("policy") == "1"
    enabled_count = sum(1 for c in CONSENTS if c["enabled"])

    user_name = "Marco Reyes"
    context = {
        "active_nav": "security",
        "region": "Kathmandu Valley region",
        "user_name": user_name,
        "user_role": "Field Coordinator",
        "user_initials": get_initials(user_name),
        "units_on_duty": 247,
        "encrypted_channels": ENCRYPTED_CHANNELS,
        "consents": CONSENTS,
        "enabled_consents_count": enabled_count,
        "deletion_request": DELETION_REQUEST,
        "show_policy": show_policy,
        "message": LAST_MESSAGE,
        "error": LAST_ERROR,
    }

    LAST_MESSAGE = None
    LAST_ERROR = None
    return render_template("index.html", **context)


@app.route("/<any(dashboard, report, map, incidents, alerts, admin):page>")
def section_view(page):
    user_name = "Marco Reyes"
    return render_template(
        "index.html",
        active_nav=page,
        region="Kathmandu Valley region",
        user_name=user_name,
        user_role="Field Coordinator",
        user_initials=get_initials(user_name),
        units_on_duty=247,
        encrypted_channels=ENCRYPTED_CHANNELS,
        consents=CONSENTS,
        enabled_consents_count=sum(1 for c in CONSENTS if c["enabled"]),
        deletion_request=DELETION_REQUEST,
        show_policy=False,
        message=None,
        error=None,
    )


@app.route("/security/consent", methods=["POST"])
def save_consent():
    global LAST_MESSAGE, LAST_ERROR
    action = request.form.get("action", "save")

    if action == "revoke_all":
        for item in CONSENTS:
            item["enabled"] = False
        LAST_MESSAGE = "All third-party sharing consents revoked."
    else:
        for item in CONSENTS:
            item["enabled"] = request.form.get(item["key"]) == "on"
        LAST_MESSAGE = "Third-party consent preferences saved."

    LAST_ERROR = None
    return redirect(url_for("home"))


@app.route("/security/deletion", methods=["POST"])
def request_deletion():
    global LAST_MESSAGE, LAST_ERROR
    action = request.form.get("action", "submit_deletion")

    if action == "cancel_deletion":
        DELETION_REQUEST["requested"] = False
        DELETION_REQUEST["reason"] = None
        DELETION_REQUEST["updated_at"] = None
        LAST_MESSAGE = "Account and data deletion request cancelled."
        LAST_ERROR = None
        return redirect(url_for("home"))

    confirm = request.form.get("confirm_phrase", "").strip()
    reason = request.form.get("reason", "Privacy preferences")

    if confirm != "DELETE":
        LAST_ERROR = "Please type DELETE in capital letters to confirm your deletion request."
        LAST_MESSAGE = None
        return redirect(url_for("home"))

    DELETION_REQUEST["requested"] = True
    DELETION_REQUEST["reason"] = reason
    DELETION_REQUEST["updated_at"] = datetime.now().strftime("%I:%M %p")
    LAST_MESSAGE = "Account and data deletion request submitted."
    LAST_ERROR = None
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)