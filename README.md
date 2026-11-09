# l09g-xiaomi-russification

Getting Russian language working on a **Xiaomi Mi Smart Speaker L09G** (a Google Assistant / Cast device) whose Google Home app UI refuses to let you pick `ru` as the assistant language, even though the speaker's own firmware fully supports it.

## TL;DR

The blocker was never the device — it's the Google Home app's UI. The L09G firmware happily reports Russian as a supported locale:

```
GET https://<speaker-ip>:8443/setup/supported_locales
→ {"locale":"ru","display_string":"Russian - русский"}  (one of 59 locales)
```

Two working paths, no MITM/root/custom-firmware required:

- **Path A — account-level (easiest).** Set the Google Assistant language for your account to Russian. Any *new* speaker on that account then boots up already in Russian during setup.
- **Path B — device-level (for a speaker already stuck on English).** Pull a device auth token (`cast-local-authorization-token`, aka LAT) for the speaker from Google's homegraph API, then write the locale directly:
  ```
  POST https://<speaker-ip>:8443/setup/set_eureka_info
  Header: cast-local-authorization-token: <LAT>
  Body:   {"settings":{"locale":"ru"}}
  ```
  The body must be nested under `"settings"` — a flat `{"locale":"ru"}` returns `200 OK` but silently does nothing.

Confirmed to survive a speaker reboot. Wiped by a factory reset (recipe just needs re-running afterward).

Full writeup with the exact token-retrieval steps: [`docs/SUCCESS-russian-L09G-2026-07-24.md`](docs/SUCCESS-russian-L09G-2026-07-24.md).

## Repo layout

```
tools/
  russify-speaker.sh      # entrypoint: ./tools/russify-speaker.sh <speaker-ip> [locale]
  russify_speaker.py      # pulls master-token -> LAT via homegraph, POSTs the locale over LAN
  cast-mic-probe/         # Cast Custom Receiver probe for built-in mics (see docs)

docs/
  SUCCESS-russian-L09G-2026-07-24.md         # the recipe that actually worked
  HOWTO-russify-google-speaker.md            # step-by-step how-to
  ARCHITECTURE.md                            # design for a (conceptual) MITM-based bootstrap pipeline
  attack-vectors-plan-2026-07-24.md          # enumeration of approaches tried/considered
  session-report-2026-07-24-russification-attempt.md
  google-assistant-mitm-russification-l09g.md
  google-home-onboarding-re-report.md
  l09g-device-teardown-research.md
  l09g-ota-first-look-2026-11-08.md          # OTA 1.44.27 / 1.52.56, testkey, Xiaomi HDR1
  l09g-ssh-and-cast-mic-2026-11-09.md        # Dropbear closed on stable-channel; Cast getUserMedia probe
  HANDOFF-voice-replacement-l09g.md          # prompt for the next agent: replace Assistant with Hermes
  historical-mitm-instruction-memu-2019.md   # older MITM-based approaches (2019, 2022) that no
  historical-mitm-instruction-ruimg-2022.md  # longer reliably reproduce in 2026
  4pda-post.md                               # writeup drafted for posting to 4pda.to

secrets/                  # gitignored — holds the account master-token locally, never committed
```

## Using `tools/russify-speaker.sh`

Requirements:
- A rooted Android phone with `adb`, on the same Wi-Fi as the speaker (the speaker's local HTTPS API isn't reachable directly from a Mac over Wi-Fi in this setup).
- Python 3 (the script bootstraps its own venv with `glocaltokens` + `gpsoauth` on first run).
- `secrets/google-master-token.txt` containing the Google account master-token (see the SUCCESS doc for how to obtain it — via a browser `oauth_token` from `accounts.google.com/EmbeddedSetup`, since app-password login is dead for this flow).

```
./tools/russify-speaker.sh <speaker-ip> [locale=ru]
```

It finds the speaker's device LAT via the account's homegraph, then writes the locale directly to the device. Nothing secret is printed to stdout.

## Note on the `docs/` MITM material

Several docs describe MITM-proxy-based approaches (`ARCHITECTURE.md`, `google-assistant-mitm-russification-l09g.md`, the `historical-mitm-instruction-*.md` files). These are kept for context/history — the MITM route is what people historically used and what old guides describe, but it did **not** end up being the working solution here; it's superseded by the direct device-API approach above. They're included because they document real research and are referenced from the session/attempt reports.

## Security notes

- `secrets/` is gitignored and must never be committed — it holds a Google account master-token, which is equivalent to full account access.
- If a master-token is ever exposed, revoke it immediately via [myaccount.google.com/device-activity](https://myaccount.google.com/device-activity) (sign out of all sessions invalidates it).
- This repo documents personal use against the author's own hardware/account, not a general exploit against Google or Xiaomi infrastructure.
