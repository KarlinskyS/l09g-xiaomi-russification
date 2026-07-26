#!/usr/bin/env python3
"""Русификация Google-Assistant колонки (Mi Smart Speaker / Cast Audio) одной командой.

Использование:
    russify_speaker.py <speaker-ip> [locale]

- <speaker-ip> — локальный IP колонки в домашней сети (её видит ТЕЛЕФОН по adb; Mac по Wi-Fi
  может не видеть). Узнать IP: в приложении Google Home открыть колонку, либо
  adb shell 'for i in $(seq 2 254); do curl -sk --max-time1 https://192.168.1.$i:8443/setup/eureka_info|grep -q cast_build && echo .$i; done'
- [locale] — по умолчанию 'ru'.

Что делает: читает сохранённый master-token (secrets/google-master-token.txt), добывает device-LAT
всех колонок аккаунта через homegraph, и записью POST /setup/set_eureka_info {"settings":{"locale":...}}
(с телефона через adb) переводит указанную колонку. Секреты в вывод не печатаются.

Требует: adb с подключённым рутованным телефоном в той же сети; venv с glocaltokens+gpsoauth
(поднимается скриптом russify-speaker.sh).
"""
import os, sys, subprocess, tempfile
from datetime import datetime
import gpsoauth
from glocaltokens.client import GLocalAuthenticationTokens

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, "secrets", "google-master-token.txt")
EMAIL = "4923920@gmail.com"
ANDROID_ID = "3d5edf8f2b0e9a11"

def die(msg, code=1):
    print("ОШИБКА:", msg); sys.exit(code)

def main():
    if len(sys.argv) < 2:
        die("укажи IP колонки: russify_speaker.py <speaker-ip> [locale]")
    ip = sys.argv[1]
    locale = sys.argv[2] if len(sys.argv) > 2 else "ru"

    if not os.path.exists(MASTER):
        die(f"нет master-token: {MASTER}")
    master = open(MASTER).read().strip()

    # access-token (обходим баг glocaltokens.get_master_token)
    res = gpsoauth.perform_oauth(EMAIL, master, ANDROID_ID,
        service="oauth2:https://www.google.com/accounts/OAuthLogin",
        app="com.google.android.apps.chromecast.app",
        client_sig="24bb24c05e47e0aefa68a58a766179d9b613a600")
    if "Auth" not in res:
        die(f"perform_oauth не дал токен: { {k:v for k,v in res.items() if k!='Auth'} } (master-token протух? перевыпусти через oauth_token)")
    g = GLocalAuthenticationTokens(master_token=master, username=EMAIL, android_id=ANDROID_ID)
    g.access_token = res["Auth"]; g.access_token_date = datetime.now()
    hg = g.get_homegraph()
    if hg is None:
        die("homegraph = None")

    lats = []  # (name, model, lat)
    for item in hg.home.devices:
        if not item.local_auth_token:
            continue
        model = ""
        try: model = item.hardware.model
        except Exception: pass
        lats.append((item.device_name or "", model, item.local_auth_token))
    speakers = [x for x in lats if "speaker" in x[1].lower() or "mi smart" in x[1].lower()] or lats
    print(f"колонок с LAT в аккаунте: {len(speakers)} (перебираю LAT против {ip})")

    def adb_curl(lat, body=None):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(lat); latfile = f.name
        subprocess.run(["adb", "push", latfile, "/data/local/tmp/lat.txt"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.unlink(latfile)
        if body is None:
            cmd = f"curl -sk --max-time 5 'https://{ip}:8443/setup/eureka_info'"
        else:
            cmd = ("curl -sk -X POST 'https://%s:8443/setup/set_eureka_info' "
                   "-H 'Content-Type: application/json' -H 'Origin: https://www.google.com' "
                   "-H \"cast-local-authorization-token: $(cat /data/local/tmp/lat.txt)\" "
                   "--data '%s' -w '|HTTP:%%{http_code}' --max-time 8") % (ip, body)
        out = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True).stdout
        subprocess.run(["adb", "shell", "rm", "-f", "/data/local/tmp/lat.txt"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out

    body = '{"settings":{"locale":"%s"}}' % locale
    import json
    for name, model, lat in speakers:
        resp = adb_curl(lat, body)
        # читаем локаль этим же LAT
        info = adb_curl(lat, None)
        cur = None
        try: cur = json.loads(info).get("locale")
        except Exception: pass
        code = resp.split("HTTP:")[-1] if "HTTP:" in resp else "?"
        print(f"  LAT('{name}'/{model}): write HTTP={code}, locale сейчас={cur}")
        if cur == locale:
            print(f"\n✅ ГОТОВО: колонка {ip} переведена на '{locale}' (совпал LAT устройства '{name}').")
            return
    die(f"ни один LAT не сменил локаль на '{locale}' на {ip}. "
        "Проверь: колонка привязана к этому аккаунту, в сети, IP верный.", 2)

if __name__ == "__main__":
    main()
