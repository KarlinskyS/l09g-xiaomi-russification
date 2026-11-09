"""Launch a Custom Receiver on one idle L09G and collect the four mic-probe results.

Intended to run inside the NAS container `hermes-netguard`, which already has
`/app/cast.py` (Cast v2 session, stdlib). Does not change volume. STOPs the app
when the probe arrives or on timeout. Refuses to run if the speaker is already
busy.

Session.wait() returns the *payload* dict, not the Cast envelope. Predicates
still see the envelope (`m["payload"]`); the value returned to us does not
contain `namespace`. Filter on payload `type == "probe"`.
"""
import json
import os
import sys

sys.path.insert(0, "/app")
import cast as C  # noqa: E402

NS = "urn:x-cast:hermes.micprobe"
IDLE_APPS = C.IDLE_APPS
APP_ID = os.environ.get("CAST_APP_ID", "").strip()
SPEAKER = os.environ.get("CAST_SPEAKER_IP", "192.168.1.118").strip()
TIMEOUT = float(os.environ.get("CAST_PROBE_TIMEOUT", "25"))
KITCHEN = "192.168.1.209"


def main():
    if not APP_ID or APP_ID in ("CC1AD845", "E8C28D3C"):
        print(
            "need CAST_APP_ID of our Custom Receiver (not Default Media Receiver)",
            file=sys.stderr,
        )
        return 2
    if SPEAKER == KITCHEN:
        print("refusing kitchen speaker (Network Guardian greetings)", file=sys.stderr)
        return 2
    s = C.Session(SPEAKER, timeout=10)
    try:
        status = s.receiver_status()
        apps = status.get("applications") or []
        busy = [
            a
            for a in apps
            if a.get("appId") not in IDLE_APPS and not a.get("isIdleScreen")
        ]
        if busy:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "reason": "busy",
                        "app": busy[0].get("displayName"),
                    },
                    ensure_ascii=False,
                )
            )
            return 3
        rid = s.send("receiver-0", C.NS_RECV, {"type": "LAUNCH", "appId": APP_ID})
        st = s.wait(
            lambda m: (m["payload"] or {}).get("requestId") == rid
            or any(
                a.get("appId") == APP_ID
                for a in ((m["payload"] or {}).get("status") or {}).get("applications")
                or []
            ),
            20,
        )
        if st.get("type") == "LAUNCH_ERROR":
            print(
                json.dumps(
                    {"ok": False, "reason": "launch_error", "detail": st},
                    ensure_ascii=False,
                )
            )
            return 4
        app = next(
            (
                a
                for a in (st.get("status") or status.get("applications") or [])
                if a.get("appId") == APP_ID
            ),
            None,
        )
        if not app:
            status = s.receiver_status()
            app = next(
                (
                    a
                    for a in (status.get("applications") or [])
                    if a.get("appId") == APP_ID
                ),
                None,
            )
        if not app:
            print(
                json.dumps(
                    {"ok": False, "reason": "app_not_in_status", "status": st},
                    ensure_ascii=False,
                )
            )
            return 4
        transport = app["transportId"]
        s.send(transport, C.NS_CONN, {"type": "CONNECT"})
        probe = None
        try:
            probe = s.wait(
                lambda msg: (msg.get("payload") or {}).get("type") == "probe",
                TIMEOUT,
            )
        except C.CastError:
            probe = None
        s.send("receiver-0", C.NS_RECV, {"type": "STOP"})
        print(
            json.dumps(
                {
                    "ok": probe is not None,
                    "speaker": SPEAKER,
                    "appId": APP_ID,
                    "displayName": app.get("displayName"),
                    "namespaces": app.get("namespaces"),
                    "probe": probe,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if probe else 5
    finally:
        try:
            s.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
