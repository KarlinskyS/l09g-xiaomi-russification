# Handoff: замена голосового ассистента на Xiaomi L09G (Grok + Hermes)

> Промпт для следующего агента. Передаётся работа по проекту `home-ru`.
> Дата передачи: 2026-11-08, дополнение 2026-11-09.

## 0. Кто ты и что от тебя нужно

Ты продолжаешь домашнее reverse-engineering / security-исследование **собственных колонок
пользователя** (Xiaomi Mi Smart Speaker L09G, 3 шт., все принадлежат владельцу,
аккаунт `4923920@gmail.com`). Это законно: железо и аккаунт — пользователя, доступ
авторизован. Работа ведётся на устройстве-доноре (одна из колонок выделяется под опыты).

**Важно про границы.** Легитимно и в скоупе: физический доступ (UART/загрузчик),
разбор дампа прошивки, поиск забытых отладочных/заводских режимов, модификация прошивки
на своём устройстве, локальные сервисы устройства. **Вне скоупа** (и предыдущему агенту
это резал автоматический фильтр): разработка эксплойтов для удалённой компрометации
облачных сервисов Google или фаззинг закрытого сетевого стека Google с целью RCE. Если
упрёшься в это — скажи пользователю прямо, не изображай деятельность. Формулируй задачи
как «модификация своего устройства», а не «взлом».

## 1. Конечная цель

Заменить Google Assistant на колонке на **свой голосовой стек**, используя **встроенные
микрофоны колонки** (без внешних спутников-ESP32 — пользователь это отверг, хочет «красиво»):

```
[микрофоны L09G] → хотворд («Гермес») → голосовой API xAI (Grok) → агент Hermes → синтез речи → динамик L09G
```

Hermes — автономный агент (Nous `hermes-agent`), живёт на сервере `blessly` (`/root/.hermes`),
есть API-сервер и OpenAI-совместимые эндпоинты (репозиторий `../hermes`). К нему подключиться
несложно — узкое место именно в колонке.

**Предпочтительная архитектура — вариант A:** получить root в стоковой прошивке, заглушить
сервис Google Assistant, поставить свой демон, который читает микрофоны и ходит в Grok/Hermes.
Cast при этом можно оставить. Вариант B (снести ОС, поставить свой Linux) — отвергнут:
придётся заново писать драйверы микрофонного массива/усилителя/LED, месяцы работы, хуже
результат.

## 2. Что за устройство (факты, подтверждены)

- **SoC:** Amlogic AXG (A113, Cortex-A53 ×4), board id `axg_s420_v1_gva`.
- **Флеш:** 2 ГБ NAND Toshiba TC58NVG1S3HBAI4, UBI поверх MTD.
- **Wi-Fi:** RTL8821CS (SDIO). **Ядро:** Linux 4.9.113 (Android-модифицированное).
- **Прошивка:** Google Cast `1.52.272222`, `system_build_number 1.52.56`, канал `stable-channel`,
  `build_type=2` (**user build**, не отладочная). Google её ещё обновляет — «старая железяка»
  только по дате выпуска, софт свежий.
- **U-Boot** `2015.01`, полный набор команд (nand/mmc/mtdparts/ubi/fastboot-amlogic),
  env: `bootdelay=1`, `factory_mode=0`, `active_slot=normal`, SELinux `enforcing`.
- **UART:** 3-контактный разъём на плате, 115200 8N1, TTL **3.3 В**.
- **Разметка NAND:** bootloader / tpl / recovery / boot / system / **chrome (самый большой —
  Cast/Assistant-стек)** / factory / data. Точные оффсеты — в `docs/l09g-device-teardown-research.md`.
- Публичного рабочего root/shell после загрузки Android **никто не получил** (последние
  подвижки — xiaoai-patch / OpenWrt forum, ~2023). Готового рецепта под L09G нет — это R&D.

## 3. Сеть и доступ (подтверждено 2026-11-08)

- 3 колонки, все `Mi Smart Speaker`, IP по DHCP и **меняются**. На 2026-11-08:
  Главная спальня `.116` (locale `ru`), Ванная `.118` (`en-US`), Кухня `.209` (`en-US`).
  Все три на одной прошивке. Колонка под опыты — **Ванная (.118)**.
- **Mac достаёт до колонок напрямую.** Прежнее «Mac не видит, нужен телефон» было из-за
  устаревшего IP `.169`, а не изоляции сети. Телефон-донор для локального API **не нужен**.
- Поиск колонок: `dns-sd -B _googlecast._tcp local.` → `dns-sd -L <name> _googlecast._tcp local.`
  → `dscacheutil -q host -a name <uuid>.local`.
- **LAT (device local auth token)** добывается с Mac из сохранённого master-token
  (`secrets/google-master-token.txt`, 600, в .gitignore) через `gpsoauth.perform_oauth`
  (app `com.google.android.apps.chromecast.app`, sig `24bb24c05e47e0aefa68a58a766179d9b613a600`,
  service OAuthLogin) → `glocaltokens get_homegraph().home.devices[].local_auth_token`.
  Рабочий скрипт-образец: `tools/russify_speaker.py`. venv: `glocaltokens`, `gpsoauth`.
- Русификация этих колонок уже сделана ранее (`docs/SUCCESS-russian-L09G-2026-07-24.md`):
  `POST https://<ip>:8443/setup/set_eureka_info {"settings":{"locale":"ru"}}` + заголовок
  `cast-local-authorization-token: <LAT>`. Это образец того, как писать в устройство.

## 4. Что уже сделано и ЗАКРЫТО (не повторяй)

Полная сетевая разведка ванной колонки (.118), только чтение, устройство не менялось:

- **nmap -p- :** открыто 8 TCP-портов: `8008` (Cast http), `8009` (Cast control TLS),
  `8443` (setup API), **`8012`** (gRPC), `9000`, `10001`, **`10007`** (gRPC), `10101`.
- **8012 и 10007 — gRPC поверх h2, принимают запросы без клиентского серта**, НО
  server reflection выключен (любой метод → `grpc-status: 12` unimplemented). Имён методов
  не подобрать вслепую.
- **9000/10001/10101** — бинарный TLS, на HTTP/h2 не отвечают (`sslv3 alert handshake failure`).
  Серверный серт: `CN=Mi Smart Speaker` (Xiaomi Cast), цепочка до `Amlogic GVA Manufacturer Cert`.
  Протокол не идентифицирован.
- **APK Google Home 4.37.27.0** скачан (apkeep/APKPure), подпись Google проверена
  (`24bb24c0...`), строки из всех 8 `.dex` извлечены. Приложение знает у колонки **только
  порты 8009/8008/8443**. Портов 8012/10007/9000/10001/10101 в приложении **нет**. Все 50
  найденных gRPC-сервисов — **облачные** (`google.internal.home.foyer.v1.*` и т.п.), не
  на устройстве. → из приложения имена device-side gRPC-методов не достать.
- **Локальный API 8443 с валидным LAT:** перебраны вероятные отладочные эндпоинты —
  `setup/{debug,dev,developer,adb,shell,logs,bugreport,get_logs,diagnostics,factory,flags,
  settings,statistics,test}` → все **404**. `check_ready_status`/`notifications` → 405.
  Рабочие только штатные (eureka_info, wifi, bluetooth, alarms, mic_mute_status, offer).
- **Дамп `eureka_info`:** `opencast_supported=false`, `build_type=2`, `proxy.mode=system`,
  переключателя «dev mode / отладка» в настройках **нет**. Полный дамп полей — в выводе сессии.

**SSH / Dropbear (закрыто 2026-11-09).** В OTA 1.52.56 есть `dropbearmulti` 2016.74 с
обёрткой Google/Xiaomi. Init стартует `sshd -G -r /etc/rsa_host_key -F`, но обёртка
читает `ro.product.release.track`, на `stable-channel` пишет `disabled on stable-channel`
и делает `exit(1)` **до** `listen()`. Поэтому в полном TCP-скане SSH нет. В **этом**
бинарнике `-G` — алиас `-B` (allowblankpass), в стоковом Dropbear `-G` означает группу;
на практике это неважно: слушателя нет. Подбор пароля не делать.

**OTA без UART (закрыто как практический путь доставки).** Официальные 1.44.27 и 1.52.56
внутри подписаны публичным AOSP testkey; оболочка Xiaomi HDR1 проверяется отдельно.
Штатного LAN-способа положить свой ZIP в `/cache/ota.zip` не найдено. Testkey сам по
себе установку не даёт. Подробности: `docs/l09g-ota-first-look-2026-11-08.md`.

**Вывод по чисто сетевым путям: SSH и OTA-доставка закрыты.** Остался один штатный
программный кандидат к микрофону — Cast Custom Receiver + `getUserMedia` (см. §5 и
`docs/l09g-ssh-and-cast-mic-2026-11-09.md`). Дальше — UART или отдельная находка
в сетевом сервисе.

## 5. Что НЕ пробовали (кандидаты)

Физика (главный путь):
- **UART → U-Boot.** Адаптер USB-UART **3.3 В** (CP2102 / FT232RL с джампером 3.3) — у
  пользователя заказывается. Первый заход — **только чтение**: снять полный лог загрузки,
  понять, включён ли **secure/verified boot** (подпись образов). От этого зависит ВСЁ.
- **Дамп разделов** через U-Boot (`nand read` / `md.b` → image), затем распаковка
  `boot`/`recovery`/`system`/`chrome`, поиск `ro.secure`/`ro.debuggable`/`factory_mode`,
  анализ сервиса Ассистента и пути аудио с микрофонов.
- **`factory_mode=1` через U-Boot env** — на части Xiaomi/Amlogic открывает adb/root на
  загрузке. На L09G не проверено — **кандидат №1** для быстрой проверки.
- **RAM-boot патченного boot.img** (adb+root включены, SELinux permissive) **без записи во
  флеш** — безопасная проба: после ребута колонка в исходном состоянии.

Сеть/радио (слабее, но дёшево):
- **miIO**-зондирование (Xiaomi, обычно UDP `54321`) — порты 9000/10001/10101 пахнут
  проприетарным Xiaomi-конфигом; проверить miIO handshake/`miio_info`.
- **proxy.mode** в eureka_info → настроить MITM и посмотреть OTA/update-трафик (unsigned HTTP?
  маловероятно, но не проверялось). Это путь к подмене прошивки, не к RCE.
- **BLE setup-канал** (GATT Weave-setup, таблица характеристик в
  `docs/google-home-onboarding-re-report.md`) — `set_eureka_info` и пр. доступны и по BLE;
  вдруг там меньше проверок, чем по HTTP.
- **Cast web receiver + `getUserMedia`** — **следующий программный шаг, подготовка
  готова, live не запускался.** Chromium даёт mic, если глобальный
  `kAllowUserMediaAccess` **или** per-app `allow_media_access_`. Глобальный флаг в
  `process.json` / `start_cast_shell.sh` 1.52.56 не включён; per-app на произвольном
  Custom Receiver ждать неоткуда, но это измеряется только запуском. Нужны App ID в
  Cast Developer Console и публичный HTTPS. Sender URL не подставляет. Четыре
  результата, не больше: receiver стартовал; есть ли `mediaDevices`; что вернул
  `getUserMedia({audio:true})`; если поток — реальный сигнал с микрофонов. Файлы:
  `tools/cast-mic-probe/`. Кухню `.209` не трогать. Если media access выключен —
  generic Custom Receiver дальше не крутить. Даже успешный PCM ≠ постоянное
  прослушивание «Гермес»: это критерий 1; критерий 2 (автономная сессия) — отдельно.

Чего делать НЕ надо: охота за 0-day в облачном/сетевом стеке Google (вне скоупа, режется
фильтром и бесперспективно по времени).

## 6. Рекомендованный порядок

1. **Cast getUserMedia live** на доноре `.118`, как только есть App ID + HTTPS
   (`tools/cast-mic-probe/`, критерии в `docs/l09g-ssh-and-cast-mic-2026-11-09.md`).
   Это последний найденный штатный софт-путь к микрофону без UART/root.
2. Дождаться UART-адаптера. Публичная база по L09G/Amlogic AXG и xiaoai-patch уже
   частично собрана (OTA, teardown, эта заметка).
3. UART: лог загрузки → ответ на вопрос «есть ли verified boot».
4. Если secure boot мягкий/частичный → RAM-boot с adb+root → §1 (свой голосовой демон).
5. Параллельно, дёшево и без железа: miIO на 9000/10001/10101; BLE-канал.
6. Если UART упрётся в жёсткий verified boot с ключом в SoC **и** getUserMedia окажется
   выключен — честно сказать, что софт-замена ассистента на этой модели без железа
   нереалистична, и обсудить компромиссы.

## 7. Ссылки в репозитории

- `docs/l09g-device-teardown-research.md` — железо, U-Boot, разметка NAND, UART, источники.
- `docs/l09g-ota-first-look-2026-11-08.md` — OTA 1.44.27/1.52.56, testkey, HDR1, пути updater.
- `docs/l09g-ssh-and-cast-mic-2026-11-09.md` — SSH закрыт; подготовка Cast getUserMedia.
- `docs/SUCCESS-russian-L09G-2026-07-24.md` — рабочий рецепт записи в устройство (LAT + 8443).
- `docs/attack-vectors-plan-2026-07-24.md` — ранее продуманные векторы.
- `docs/google-home-onboarding-re-report.md` — разбор онбординга, BLE GATT-характеристики.
- `tools/russify_speaker.py` — образец получения LAT и записи в 8443.
- `tools/cast-mic-probe/` — Custom Receiver + sender для четырёх результатов getUserMedia.
- Память проекта: `l09g-russian-solved`, `l09g-voice-replacement-research`, `donor-phone-context`.
- Hermes: `../hermes` — **другой репозиторий**. Туда L09G-исследование не писать.
  Network Guardian (`cast.py` в контейнере `hermes-netguard`) — только транспорт пробы.

## 8. Среда (на момент передачи)

- Mac (darwin). Из домашней сети `192.168.1.0/24` колонки доступны напрямую. 9 ноября
  ноутбук сидел в корпоративной `Menora_Employee` — пробы шли через `ssh nas` и
  `docker exec -i hermes-netguard python3` (`-i` обязателен, иначе stdin пустой).
  На хосте NAS системного `python3` нет.
- Инструменты стоят: `nmap`, `apkeep`, `jadx`, `apktool`, `openssl`, `dns-sd`, Ghidra 12.2.
- venv с `glocaltokens`+`gpsoauth` поднимается из `tools/russify-speaker.sh`.
- Телефон-донор (Mi 8, adb, Magisk, bootloader залочен) — для этой задачи **не нужен**, но
  на нём живёт аккаунт-владелец; не ресетить (см. память `donor-phone-context`).
- Репозиторий этого проекта: `/Users/ieffai/code/home-ru`, remote
  `KarlinskyS/l09g-xiaomi-russification`. Не путать с `/Users/ieffai/code/hermes`.
