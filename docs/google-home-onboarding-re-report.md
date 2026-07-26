# Google Home — Reverse Engineering отчёт: onboarding новой колонки

- Приложение: `com.google.android.apps.chromecast.app` (Google Home)
- Версия: 4.22.28.0
- Источник: `Google+Home+4.22.28.0.apks` (split APKs: base.apk + config.ru.apk + density/abi конфиги)
- Инструменты: jadx 1.5.6 (Java-декомпиляция dex, `--no-res`), apktool 3.0.3 (ресурсы/манифест)
- Код прогнан через R8/ProGuard: большинство классов лежит в `defpackage/*.java` с короткими бессмысленными именами (`ajlk`, `aikc`, `koo`, ...). Activity/Fragment верхнего уровня сохранили читаемые имена в пакете `com/google/android/apps/chromecast/app/**`. Строковые литералы (URL, RPC-имена, intent-keys, Phenotype-ключи) ProGuard не переименовывает — на них и построен поиск.
- Все пути ниже — относительно `jadx-out/sources/`.

Релевантные пакеты онбординга, найденные в дереве:
```
com/google/android/apps/chromecast/app/setup/**
com/google/android/apps/chromecast/app/setup/bluetooth/**
com/google/android/apps/chromecast/app/setup/discovery/**
com/google/android/apps/chromecast/app/nest/setup/**
com/google/android/apps/chromecast/app/wifi/setup/**
com/google/android/apps/chromecast/app/concierge/flows/setup/**
com/google/android/apps/chromecast/app/setup/thirdpartyconcierge/**
```

---

## 1. Endpoint'ы, вызываемые в онбординге

Два независимых канала связи + BLE-фоллбек.

### 1.A. Локальный HTTPS API самой колонки

Классическая Cast/Eureka-схема. Базовый URL строится в `defpackage/ajlk.java:30-35`:

```java
String str3 = z ? "https" : "http";
return new URI(str3, null, ahtr.a /*host=IP колонки*/, z ? ahtr.c : ahtr.b /*port*/, "/setup/".concat(str), query, null);
```

т.е. каждый запрос — `https://<device-ip>:<port>/setup/<endpoint>`.

Хост/порт — `defpackage/ahtr.java` (Parcelable: `a`=host, `b`=http-порт, `c`=https-порт), заполняются из `defpackage/ahtq.java:356-381`. Дефолтные значения портов — Phenotype-флаги в `defpackage/bnnc.java:162-166`:

```
"45356384" -> 8443L              // https-порт по умолчанию
"45356387" -> "8009,8008,8443."  // список портов при обнаружении
"45356389" -> 8008L              // http-порт по умолчанию
```

Базовый клиент запросов — `defpackage/ajlk.java` (GET/POST хелперы), заголовки `Origin: https://www.google.com`, `cast-local-authorization-token` (LAT).

Коды результата — enum `defpackage/ajkk.java`: `OK, BAD_REQUEST, ERROR, TIMEOUT, INVALID_RESPONSE, ACCESS_DENIED, BLE_CONNECTION_ERROR, HTTPS_CONNECTION_ERROR, LAT_ERROR, LAT_NOT_LINKED, LAT_MISMATCH, LAT_MISSING, HOTSPOT_ERROR*, CERTIFICATE_MISSING, INVALID_STATE, SSL_CERTIFICATE_UNTRUSTED, ...`

Setup-состояния устройства — enum `defpackage/ahtm.java`: `DISCONNECTED, SCANNING, SCANNING_WRONG_SSID, BEING_CONFIGURED[_WRONG_PASSWORD], OBTAINING_IP_ADDRESS, CHECKING_GLOBAL_CONNECTIVITY[...], CONNECTED, CONNECTED_TOS_NOT_ACCEPTED, CONNECTED_GAIA_REQUIRED, CONNECTED_WOCA_PENDING, CONNECTED_REALM_PENDING`.

`defpackage/ahtq.java:565-769`, метод `ai()` — парсинг ответа `GET /setup/eureka_info`, восстанавливает классические поля: `version, name, cast_build_revision, manufacturer, model_name, mac_address, ip_address, bssid, ssid, wpa_state, setup_state, public_key, certificate, intermediate_certs, ssid_suffix, groups, timezone, locale, country_code, pin_code, device_id, ...`

Найденные endpoint'ы:

| Endpoint | Класс:строка | Данные |
|---|---|---|
| `GET /setup/eureka_info?params=...&options=...&nonce=...` | `ajie.java:154` | статус устройства → `ahtq` (device info, wifi state, setup_state, сертификат) |
| `GET /setup/scan_wifi` | `ajla.java:17` | инициирует сканирование Wi-Fi |
| `GET /setup/scan_results` | `ajij.java:23` | список найденных SSID |
| `POST /setup/set_network_ssid` `{ssid}` | `ajle.java:23,33` | установка целевого SSID |
| `POST /setup/connect_wifi` `{ssid,wpa_auth,wpa_cipher,wpa_id,scan_ssid,enc_passwd\|passwd}` | `ajlo.java:24-45,51` | пробное подключение (класс `ajdj` = WifiConfig) |
| `POST /setup/set_network` | `ajld.java:24-36` | аналог connect_wifi |
| `POST /setup/save_wifi` `{keep_hotspot_until_connected}` | `ajkz.java:29,34` → `{setup_state, keep_hotspot_until_connected}` | финализация подключения к сети |
| `POST /setup/forget_wifi` `{wpa_id}` | `ajhz.java:23,27` | забыть сеть |
| `POST /setup/set_eureka_info` `{...}` | `ajlc.java:32` | запись полей на устройство (страна, имя, DeviceInfo) |
| `GET /setup/get_app_device_id` `{app_id="E8C28D3C"}` → `{app_device_id, certificate, signed_data}` | `ajic.java:19-42` | локальный сертификат приложения/подписанные данные (LAT/auth handshake) |
| `POST /setup/smart_home/actions/create_device` `{structure_id, scanned_code}` → `{device.agent_device_id}` | `ajhj.java:28-46` | устройство получает structure_id + linking code, создаёт себя в облаке |
| `POST /setup/smart_home/actions/indicate` `{sequence_id, request_id, local_id, start, structure_id}` | `ajhk.java:32-37`, вызов из `oka.java:180` (`"toggle_bootstrap_device_indication"`) | визуальное/звуковое подтверждение "это оно" |
| `POST /setup/smart_home/actions/setup` `{local_id, device_name, room_name, room_id, structure_id, sequence_id, request_id, response_on_setup_complete, pin_code, ssid, enc_passwd, wpa_auth, wpa_cipher}` | `ajhl.java:46-93`, вызов из `olt.java:343,352` (`"set_up_bootstrap_device"`) | **главный "finish_setup"-эквивалент**: Wi-Fi credentials + имя + комната + structure_id + pin_code одним запросом |
| `POST /setup/play_sound` `{sound_id}` | `ajkr.java:24,28` | идентификационный звук |
| `GET /setup/supported_locales` | `ajik.java:19` | список локалей устройства |
| `GET /setup/supported_timezones` | `ajil.java:19` | список таймзон |
| `GET /setup/offer` → `{token}` | `ajkq.java:18,27` | offers/pairing token |
| `GET /setup/license` | `ajih.java:25` | лицензионный текст |
| `POST /setup/send_log_report` `{uuid}` → `{crash_report_id}` | `ajlb.java:25,29,37` | отправка логов |
| `GET /setup/get_log_report` | `ajlk.java:83` | стриминг логов |

Прочие пост-setup эндпоинты видны в фасаде `defpackage/ajjx.java:59-562` (`set_audio_output_delay`, `notifications_enabled`, `set_night_mode`, `disband_group`, `get_clocks`, `check_assistant_ready_status`, `reboot` и др.) — не относятся к первичному онбордингу.

Активности, запускающие flow: `WifiSetupActivity.java` (ViewModel `defpackage/aajh.java`), `DeviceSetupActivity.java`, `NestPairingActivity.java`, `QrScanSetupActivity.java`, `CastAccessPointSetupActivity.java`.

Связь "облако → локальный API устройства", `defpackage/olt.java:330-343`:
```java
aikc aikcVar = this.G;                 // HomeGraph/StructuresService клиент
aihq aihqVarA = aikcVar.a();            // текущая структура/дом аккаунта
String strH = aihqVarA.H();             // structure_id
...
new ajhl(..., strR /*local_id*/, str /*device_name*/, str2 /*room*/, strH /*structure_id*/, z2, ...); // -> POST /setup/smart_home/actions/setup
```

### 1.B. BLE (Weave) GATT-провижининг

`defpackage/aghn.java` — таблица UUID GATT-характеристик Weave-setup сервиса (base `0000fea0-0000-1000-8000-00805f9b34fb`): `language, sound, version, name, public_key(+control), nonce, signed_data(+control), device_cert(+control), scan_results(+control), scan_wifi, set_network_ssid, set_network, connect_network, country, hotspot_bssid, setup_state, intermediate_certs(+control), mac_address, device_id, ssid_suffix, ip_address, reboot, save_wifi, set_eureka_info, ecdh_public_key, hmac_nonce, hmac_proof, provisioning_info(+control), sddt_account/status/packet/response(+control)`. Используется как фоллбек, если Wi-Fi/HTTP локальный канал недоступен.

### 1.C. Облачное gRPC API — Google Home Foyer

Хост: **`googlehomefoyer-pa.googleapis.com`**, порт 443 (TLS/mTLS), gRPC, пакет `google.internal.home.foyer.v1.*`.
OAuth scope: `oauth2:https://www.googleapis.com/auth/homegraph` (`aikc.java:811,925`).
Конфиг хостов/таймаутов: `bniy.java`, `bnwh.java`. Главный клиент — `defpackage/aikc.java`. RPC-дескрипторы объявляются через `bosf.c("google.internal.home.foyer.v1.<Service>", "<Method>")`.

Релевантные онбордингу RPC:

- **StructuresService** (`aikc.java:766-844`, дескрипторы `auup.java`):
  - `CreateStructure` — тело `atwf{ auuc /*Structure*/ }`, `Structure.d` = name (`aujr.java:265-271`).
  - `GetHomeGraph` (`aikc.java:874-921`, метод `l(aiik,...)`) — запрос `aueo`, ответ `aueq` (devices, rooms(`bpjs`), structure name/id, locale-структуры, сервисные аккаунты `aulj`, `atzl`).
  - `GetWeavePairingInfo` (`auup.java`) — BLE-Weave commissioning.
  - `UpdatePairingConfigurationDone` (`aijh.java`), `WakeStructureDevices`, `BatchModifyStructuresDevices`, `UpdateStructureV2`, `GetStructure`.
- **HomeDevicesService** (дескрипторы `aujr.java`):
  - `CreateDevice` (`aujr.java:43-65`, request `atvt`, response `atvu`). Вызывающая логика — `nhx.java` case 16 (703-735): лог `"Sending LinkDeviceRequest for %s."`, берётся `atvuVar.b(atxu).c(atyb).c` (device/cast id) для дальнейшей привязки.
  - `DeleteDevice` (`aujr.java:67-89`, request `atxe`).
  - `SyncDevices` (`aikc.java:951-974`, метод `o()`, request/response `auvm/auvn`) — обновляет список устройств структуры после добавления.
  - `CheckDeviceReadyState` (`tyb.java`).
  - `CoLocateUser` (`rlt.java`), вызов из `nhx.java` case 17-18 (`"Adding Tangor to structure"` → `aikc.l(aiik.REASSIGN_DEVICE, ...)`).
  - `SendEnterWeavePairingModeCommand` (`aiji.java`).
  - `UpdateDeviceWhere` (`xwj.java`) — назначение комнаты.
  - `GetDevicesAssociations` (`aujr.java:115-139`, request `audh`, response `audi`).
  - `RecordDeviceArbitrationConsent`, `UpdateDeviceFixture`, `UpdateDeviceSettings`, `GetDeviceSupervisionSettings`.
- **SetupService**: `SetupProvisioningInfo` (`vza.java`), `UnifiedPairingDevice` (`autj.java`), `ReportAccountLinkingComplete`, `UpdateTVSetupProgress`, `GetAndroidTvApplicationDetails` (линковка сторонних приложений на устройствах с экраном, `nhx.java` case 8, 255-467).
- **CHIPService** (Matter): `GetDeviceSetupData`, `UpdateChipDevice`.
- **CameraService** (тот же паттерн BLE-провижининга): `GetSetupWeavePairingNonce`, `GetSetupWeaveStart`, `SetupBluetoothAuthorize`, `SetupBluetoothStart`, `SetupBluetoothResult`.

Прочие хосты рядом с setup-кодом:
- `accountlinking-pa.googleapis.com`, `oauthintegrations.googleapis.com` — сторонняя привязка аккаунтов (`PartnerAccountLinkingActivity`/`WWGAActivity`), не сама колонка.
- `https://nestservices.google.com/partnerconnections` — Phenotype-константа (`bnnc.java:125`).
- `clients5.google.com` (`bnnc.java:150`, ключ `"45356370"`) — точное применение не идентифицировано.
- `homeplatformmesh-pa.googleapis.com` — присутствует в общем списке googleapis-хостов, прямых вызовов в setup-классах не найдено (вероятно, Matter mesh, пост-setup).

### 1.D. Облачное API привязки устройства — `clients3.google.com` (подтверждено доп. проверкой)

Отдельный, третий облачный канал, найденный дополнительно (изначально упомянут в параллельном MITM-исследовании, здесь **подтверждён прямой трассировкой кода**):

- Полный URL: `https://clients3.google.com/cast/orchestration/deviceuserlinksbatch?rt=b`
  - Базовый хост — Phenotype-флаг `"45355692"`, default `"https://clients3.google.com"` (`defpackage/bnbk.java:37`).
  - Путь собирается в `defpackage/acch.java:2290-2292`, метод `dj()`: `bnbi.a.ng().e()` (= флаг `45355692`) + `"/cast/orchestration"`.
  - Полный путь — `defpackage/teq.java`: `strDj.concat("/deviceuserlinksbatch?rt=b")`.
- Класс запроса — `defpackage/teq.java` (`CreateDeviceLinkRequest extends vpg`), парный `defpackage/ter.java` (`DeleteDeviceLinkRequest`, путь `/deletedeviceuserlink?rt=b`).
- **OAuth scope — `oauth2:https://www.google.com/accounts/OAuthLogin`** — отличается от `homegraph`-scope, используемого gRPC-каналом Foyer (п. 1.C). Это самостоятельный, более старый механизм линковки устройства к аккаунту, параллельный HomeGraph `CreateDevice` RPC.
- Тело запроса — **protobuf** (`Content-Type: application/protobuf`, класс `aqxo extends bkpc` — `GeneratedMessageLite`), а не JSON: `aqxo.b` — список `aqxn` (по одному на линкуемое устройство).
- Вызывается напрямую из онбординга: `com/google/android/apps/chromecast/app/setup/DeviceSetupActivity.java:557`:
  ```java
  tduVar.f(new tep(str /*ajhrVar.a = app_device_id*/, ajhrVar.b /*cast_id*/,
                    ahtqVar.bf /*intermediate certs[]*/, ahtqVar.l() /*wifi/network id*/,
                    null, ahtqVar.m, ahtqVar.u /*needs-language-selection flag*/,
                    ahtqVar.aA /*model code, см. akdv*/, false),
            new tiw(context, ahtqVar, 2));
  ```
  Сборка protobuf-сообщения — `defpackage/tdu.java:146-260` (метод `g(List, tdk)`), поля `aqxn`, которые реально уходят в облако:

  | Поле `aqxn` | Источник (из `tep`) | Смысл |
  |---|---|---|
  | `c` | `tepVar.b` = `ajhrVar.a` | app_device_id (из локального `/setup/get_app_device_id`) |
  | `d` | `tepVar.c` = `abmn.ao(ajhrVar.b)` | закодированный cast_id |
  | `g` | `tepVar.d` = `ahtqVar.l()` | сетевой идентификатор (SSID/подключение) |
  | `e` | `abmn.an(tepVar.k)` = intermediate certs | цепочка сертификатов устройства |
  | `f` | `tepVar.e` (если `tepVar.h`) | доп. сертификатное поле |
  | `h` | `tepVar.j` = `ahtqVar.aA` | **код модели устройства** (тот же код, что в `akdv.a/b()`) |
  | `i` | `tepVar.i` = `false` (в вызове из setup) | флаг |
  | `l` | производное от `ten.h()` (уже слинкованное устройство?) | булев |
  | `aqnc` (submessage `j`) | `c=tepVar.f`, `d=tepVar.g=ahtqVar.u` | `d` = тот же **флаг "модель требует выбора языка"**, что управляет показом `wbr` (см. Блок 3 языка) |

  **Явного отдельного поля "locale"/"language" в этом protobuf-сообщении не найдено** — есть только булев флаг "модель требует выбора языка" (`ahtqVar.u` → `aqnc.d`), но не сам код языка. Это совпадает с независимым наблюдением из параллельного MITM-исследования (`google-assistant-mitm-russification-l09g.md` в этой же папке): там тоже не удалось найти выделенное protobuf-поле локали в этом трафике, и вместо целевого патча поля использовалась грубая байтовая/строковая замена поверх сериализованного потока.

**Вывод**: это не дубликат, а самостоятельный, третий канал связи (наравне с локальным HTTPS API колонки и облачным gRPC Foyer), использующий собственный OAuth-scope и protobuf-сериализацию. Через него в облако уходит код модели устройства (`aA`/`akdv`) и флаг требования выбора языка, но не сам языковой код в чистом виде — что объясняет, почему прямая протобаф-патч-атака на локаль через этот endpoint не тривиальна и требует байтового патчинга, а не подмены конкретного поля.

### Реконструкция flow

1. Обнаружение устройства — Bluetooth/discovery (`setup/bluetooth`, `setup/discovery`) + `GET /setup/eureka_info` по локальному hotspot колонки.
2. `GET /setup/scan_wifi` + `/scan_results` — сканирование домашней сети.
3. `POST /setup/connect_wifi`/`/set_network` — пробное подключение; `POST /setup/save_wifi` — коммит.
4. Параллельно облачный вызов `StructuresService.CreateStructure`/`GetHomeGraph` — получение/создание `structure_id` текущего дома.
5. `POST /setup/smart_home/actions/create_device {structure_id, scanned_code}` — устройство создаёт себя в HomeGraph, получает `agent_device_id`.
6. `POST /setup/smart_home/actions/indicate` — визуальное/звуковое подтверждение.
7. `POST /setup/smart_home/actions/setup {local_id, device_name, room_id, structure_id, ssid, enc_passwd, wpa_auth, pin_code, ...}` — финальная передача Wi-Fi credentials + привязка к комнате/дому.
8. Приложение опрашивает `HomeDevicesService.SyncDevices`/`CheckDeviceReadyState`/`CoLocateUser`, чтобы увидеть новое устройство в HomeGraph и завершить UI онбординга.

---

## 2. Protobuf

Локальный API устройства (`/setup/*`) — **не protobuf, а JSON** (`org.json.JSONObject`), тела `application/json`.

Protobuf используется только в облачном gRPC-канале (`google.internal.home.foyer.v1`) и внутри бинарных BLE-характеристик (`signed_data`/`provisioning_info`, вероятно TLV/protobuf, парсер не идентифицирован по имени).

Ни одного `.proto`-файла как ресурса не найдено (ожидаемо для release-сборки). Java-классы, сгенерированные protoc (`GeneratedMessageLite`), переименованы R8. Соответствие установлено по контексту использования, не по строковым дескрипторам полей:

- `atvt` = CreateDeviceRequest, `atvu` = CreateDeviceResponse
- `atwf` = CreateStructureRequest(?), `auuc` = Structure
- `atow` = device-id wrapper {agent_type, id}, `atyb` = DeviceId-обёртка (`.d` = `atow`)
- `aueo` = GetHomeGraphRequest, `aueq` = GetHomeGraphResponse
- `audh` = GetDevicesAssociationsRequest, `atxe` = DeleteDeviceRequest

Пакет протоколов подтверждён строкой `"google.internal.home.foyer.v1.<Service>"`, но сами `.java`-классы физически лежат в `defpackage/*`, не под `google/internal/home/foyer/...` — R8 переместил их в общий namespace.

---

## 3. Выбор языка

Источник по умолчанию — **`Locale.getDefault()` телефона**, не выбор в UI и не язык структуры/аккаунта.

`defpackage/akek.java`:
- `akek.d()` → `e(Locale.getDefault())` — код вида `"ru-RU"`, `"en-US"`.
- `akek.c()` → `Locale.getDefault().getLanguage()` (fallback `"en"`).
- `akek.f(String)` → `Locale.forLanguageTag(str)`.

`com/google/android/apps/chromecast/app/setup/DeviceSetupActivity.java`:
- строки 911, 1088: `this.av.h = akek.d();` — язык телефона пишется в поле `h` объекта `ahtq` (см. `ahtq.java:149`).
- строка 1358: `intent.putExtra("assistantLanguageIntentKey", this.av.h);` — прокидывается дальше через intent-extra.
- строки 522-524, метод `bw()`:
  ```java
  private final boolean bw() {
      return lM().u && !koo.B(akek.d(), lM().h().ae);
  }
  ```
  `lM().u` — булев флаг устройства (модель требует явного выбора языка), `koo.B(...)` проверяет вхождение локали телефона в список поддерживаемых для семейства устройства (`lM().h().ae` — код семейства из `akdv`). Если язык не поддержан — показывается `wbr()` (экран выбора языка), иначе язык молча берётся из `Locale.getDefault()`.

Экран выбора языка — `defpackage/wbr.java` (layout `language_selection_new`, аналитика `PAGE_LANGUAGE`):
- список опций — `koo.A(bp().lM().h().ae).split(",")`.
- при выборе языка, отличного от дефолтного, — диалог-предупреждение (`language_selection_confirmation_title/body`).
- выбор пишется через `bc(str)` → `this.d.h = str` — тот же путь, что `av.h`.

Ещё один UI-компонент — `defpackage/tmk.java` (Spinner на базе `koo.A(...)`), похоже, вариант для другого setup-flow.

Список поддерживаемых языков — **client-side константы через Phenotype-флаги**:

`defpackage/koo.java`, метод `A(int i)`:
```java
public static String A(int i) {
    if (i == 43) return bnrt.a.ng().K();      // flag "45356208"
    return i == 34 ? bnrt.a.ng().J()          // flag "45356207"
                    : bnrt.a.ng().L();          // flag "45356708"
}
```

`defpackage/bnrv.java` (Phenotype-реализация, namespace `sharedPrefs_ph`):
- `45356207` (J), default: `"da-DK,de-AT,de-BE,de-CH,de-DE,en-AU,en-CA,en-GB,en-IE,en-IN,en-SG,en-US,es-ES,es-MX,es-US,fr-BE,fr-CA,fr-CH,fr-FR,it-CH,it-IT,ja-JP,ko-KR,nb-NO,nl-BE,nl-NL,sv-SE,zh-TW"`
- `45356208` (K) — идентичный список.
- `45356708` (L), default: то же + `en-ID,en-PH,en-TH,es-AR,es-CL,es-CO,es-PE,hi-IN,id-ID,pt-BR,th-TH`
- **`ru-RU` отсутствует во всех трёх списках** (проверено grep-ом).
- Проверка вхождения — `koo.B(str, i)` → `apkk.bA(list, code)` (простое сравнение по split(',')).

Дальнейшая передача: `WifiSetupActivity.java:156` читает `assistantLanguageIntentKey` → `aajhVar.n(...)`; `aajh.java:393-403` (`n(...)`) сохраняет в поле `u`, дальнейшее использование не удалось однозначно проследить (вероятно глубже, через `ahtq`-объект, в момент фактического provisioning-запроса, классы `wfc`/`wff`).

`DeviceSetupActivity.java:734-742` — момент формирования шага setup-протокола:
```java
this.av.d(2, DateFormat.is24HourFormat(...) ? ahto.HOURS_24 : ahto.HOURS_12);
...
this.av.d(3, lM().e(str2, str2.split("-")[0]));
```
язык (`str2 = this.av.h`) проходит через `lM().e(язык, базовый_язык)` — похоже на маппинг BCP-47 кода к ближайшему поддерживаемому базовому языку устройства (fallback на язык без региона) перед отправкой.

**Вывод**: язык по умолчанию берётся из `Locale.getDefault()` телефона, НЕ из аккаунта/структуры дома. Явный экран выбора языка показывается только если модель требует выбора **и** локаль телефона не входит в захардкоженный (через Phenotype-дефолты) список. Передаётся как строка (`"ru-RU"`) через intent-extra `assistantLanguageIntentKey`, а не отдельным protobuf-полем.

---

## 4. Где появляется ошибка

Главный enum ошибок — `defpackage/weh.java`:
```java
public enum weh {
    APP_UPGRADE, AUTO_NETWORK_SWITCH, CN_PING_FAILED, CN_START_NAT_FAILED,
    CN_SAVE_WIFI_FAILED, CN_SETUP_STATUS_BAD_AP, CN_SETUP_STATUS_DISCONNECTED,
    CN_CAPTIVE_PORTAL_NOT_SUPPORTED, CN_SETUP_STATUS_WRONG_PASSWORD,
    CN_SETUP_STATUS_WRONG_SSID, CN_SSDP_NOT_FOUND, CN_MDNS_NOT_FOUND,
    CN_OPENCAST_NOT_FOUND, CN_STATUS_POLL_ERROR, CN_STATUS_POLL_TIMEOUT,
    CN_WIFI_SWITCH_ERROR, CONNECTOR, DEVICE_NOT_FOUND, DEVICE_VALIDATION,
    GENERAL, NO_APP_DEVICE_ID, USER_CANCELLED, NETWORK_REFRESH_FAILURE,
    PLAY_SOUND_FAILURE, REBOOT_FAILURE, RESET_FAILURE, LICENSE_FETCH_FAILURE,
    OPENCAST_PIN_FETCH_FAILURE, PREVIEW_CHANNEL_FETCH_FAILURE,
    SETUP_STATE_REFRESH_FAILURE, FORGET_WIFI_FAILURE;
}
```
Покрывает неправильный SSID/пароль, устройство не найдено (mDNS/SSDP/BLE), требуется обновление приложения, ошибки валидации/сети/сертификата, тайм-ауты. Отдельных значений «неавторизован аккаунт»/«неподдерживаемая модель» нет — обрабатываются отдельными ветками (`APP_UPGRADE`, `DEVICE_VALIDATION`).

Рендеринг:
- `defpackage/wcm.java:631`, метод `lJ(int i, Bundle bundle, weh wehVar, ajkk ajkkVar, String str)` — центральный обработчик, строит диалоги через `zjp`/`zjo` и строки (`R.string.setup_ping_failed`, `R.string.device_connect_failed` и т.д.). Базовый класс, от которого наследуется `DeviceSetupActivity` (через `wau`).
- `com/google/android/apps/chromecast/app/setup/DeviceSetupActivity.java:1786` — переопределяет `lJ(...)`, добавляет специфичную логику (BLE captive-portal, wifi-connect ошибки).
- `defpackage/wff.java` — низкоуровневый класс, инициирующий Wi-Fi/BLE вызовы и генерирующий `weh`-коды (`DEVICE_NOT_FOUND`, `NO_APP_DEVICE_ID`, `DEVICE_VALIDATION`).
- `defpackage/ytz.java` (fragment, tag `"ForceUpgradeFragment"`) — экран «обновите приложение», вызывается через `wcm.aT(int i)` (строка 520). `ytz.a(int)`: `1=APP_START, 2=DEVICE_SETUP, 3=BOOTSTRAP_DEVICE_SETUP/OS_UPGRADE`.

---

## 5. Проверки

### Модель устройства

- `defpackage/akdv.java` — enum моделей (жёстко зашит в APK): `CHROMECAST_2015_AUDIO, GOOGLE_HOME, GOOGLE_HOME_MINI, GOOGLE_HOME_MAX, GOOGLE_NEST_HUB, GOOGLE_NEST_HUB_MAX, CUBE, SD_ASSISTANT, ANDROID_TV, ...` (50 значений). Каждое — короткий строковый код модели (`"a","b","k","o","p","u","w","ybc",...`), число `ae` (код семейства для UI/языков), булев `aa` («поддерживается по умолчанию»).
  - `akdv.a(str)`/`akdv.b(str)` — маппинг кода модели (от устройства) в enum через статическую хэш-карту `arhk Z`. Неизвестный код → `null`. **Чисто client-side**: список моделей полностью зашит, сервер не участвует в маппинге.
  - Пример использования: `com/google/android/apps/chromecast/app/setup/QrScanSetupActivity.java:143` — `akdv akdvVarB = akdv.b(stringExtra2);`.

- `defpackage/ahtq.java:533`, метод `ad()` — итоговая проверка «поддерживается ли модель для setup»:
  ```java
  public final boolean ad() {
      bkvu bkvuVarH = bnrt.a.ng().H();      // denylist, Phenotype flag "45356188"
      String strP = bnrt.p();                // allowlist-строка, flag "45356187", default ""
      if (bkvuVarH != null && z() && bkvuVarH.b.contains(apkk.bx(this.aA))) {
          return false;                       // модель в денилисте -> не поддерживается
      }
      return (h().aa || (strP != null && z() && Arrays.asList(strP.split(",")).contains(apkk.bx(this.aA))))
             && !Boolean.FALSE.equals(this.D);
  }
  ```
  Гибрид: `h().aa` — хардкод-enum-флаг (полностью client-side), плюс два Phenotype-флага (allowlist/denylist по коду модели), которые кэшируются в SharedPrefs и не обязательно перезапрашиваются в момент конкретного setup-сеанса.
  - Вызов: `DeviceSetupActivity.java:957` — `if (!lM().ad()) { ...; this.be = true; lJ(9, null, weh.APP_UPGRADE, null, null); }` → показывается `ForceUpgradeFragment`.

- `ahtq.java:542`, метод `ae()` — ещё одна проверка совместимости модели (`akdw.h(str, bnwu.a.ng().r())`, другой Phenotype-список).

### Версия прошивки колонки

Явной клиентской проверки (`minFirmwareVersion` и т.п.) в исследуемых setup-пакетах **не найдено**. `"firmware"` встречается только в контексте Nest-камер (`ydo.java:49`, статус `FIRMWARE_ERROR`, не колонка) и в UI отображения версии в настройках (`vue.java:52-53`), не как gate при онбординге. Либо проверка целиком на стороне устройства/сервера, либо реализована глубже внутри `opencast`-протокола, не идентифицированного по строковым литералам.

### Сертификат устройства

`weh.DEVICE_VALIDATION`, `defpackage/wff.java:520-558` — настоящая криптографическая проверка цепочки X.509-сертификатов (`ajly`/`ajhq`, метод `ajhq.c(...)`), локально на телефоне, но на основе встроенных корневых сертификатов Google.

### Версия Google-приложения на телефоне

`koo.u/v/w/x/y` + `bmyz.a.ng().i()/j()/k()`, `bmyz.d()` — минимальные versionCode, сверяются через `PackageManager.getPackageInfo(...).getLongVersionCode()`, полностью локально.

---

## 6. Можно ли обойти проверки

Client-side (потенциально обходимо патчингом APK/локального кэша, без подделки серверного трафика):

1. **Распознавание модели устройства** — `akdv.a()/b()` — статическая таблица в APK.
2. **Список поддерживаемых языков setup** — `koo.A(int)` + `bnrv.java` — дефолты зашиты как константы; Phenotype-переопределение кэшируется локально в SharedPrefs (`sharedPrefs_ph`) и не гарантированно перезапрашивается на каждый setup — т.е. при офлайне/патче используются хардкод-дефолты.
3. **Решение "показывать ForceUpgradeFragment"** (`ahtq.ad()`) — комбинация client-hardcoded `akdv.aa` + локально закэшированных Phenotype allow/denylist.
4. **Версия Google-приложения** (`koo.u/v/w/x/y`, `bmyz`) — целиком через `PackageManager`, локально.

НЕ обходимо тривиально (криптографически осмысленная проверка, а не строковое сравнение):

5. **Валидация сертификата устройства** (`DEVICE_VALIDATION`, `wff.java`) — построение X.509-цепочки на встроенных корневых сертификатах Google.

Версия прошивки колонки — проверка не найдена в клиенте, вероятно на стороне устройства/облака (обход клиента её не затронет).

---

## 7. Feature flags

Внутренний Phenotype-wrapper, `defpackage/anwc.java` — регистрация флагов. Строки, подтверждающие происхождение:
- `Log.w("PhenotypeFlag", "Setting enableAutoSubpackage on SharedPrefs-backed flags");` (строка 34)
- `throw new IllegalStateException("Cannot set GServices prefix and skip GServices");` (строка 42) — флаги имеют и Phenotype-, и GServices-путь получения значения.
- Методы `d/e/f/g/h` создают типизированные `anwe`-объекты (double/long/String/boolean/protobuf-флаги) с ключом-строкой (числовой Phenotype experiment ID) и дефолтом.

`defpackage/bnrv.java` — реализация группы `sharedPrefs_ph` (`new anwc("sharedPrefs_ph")`), ~90 флагов. Релевантные онбордингу:

| Flag ID | Тип | Назначение | Default |
|---|---|---|---|
| `45356207` | String | языки setup (список J) | см. блок 3 |
| `45356208` | String | языки setup (список K) | тот же список |
| `45356708` | String | языки setup (список L, расширенный) | список + доп. регионы |
| `45356187` | String | allowlist моделей устройств | `""` |
| `45356188` | protobuf (bkvu) | denylist моделей устройств | пустой список |
| `45356192` | String | список "локальных" устройств (Hue/Matter) | `"hue-hca,assistant-connect-clicky-1,c-by-ge,hue-hca-ble,ledvance-on-aogh,smart-local-6ec63,talula-spatula"` |
| `45356384` | Long | https-порт локального API | `8443` |
| `45356387` | String | список портов при обнаружении | `"8009,8008,8443."` |
| `45356389` | Long | http-порт локального API | `8008` |
| `45355692` | String | базовый хост облачного API привязки устройства (`defpackage/bnbk.java:37`, см. п. 1.D) | `"https://clients3.google.com"` |
| `45786124` | Long | таймаут (вероятно сетевой) | `2000` |
| `45684362` | protobuf (bkvu) | не идентифицировано точно | пустой список |
| `45786123`, `45785754` | Boolean | не идентифицировано точно | `false` |

Фасад-геттеры — `defpackage/bnrt.java` (`bnrt.p()`, `bnrt.A()` и т.д. → `a.ng()` = `bnrv`).

Тот же паттерн (`new anwc(...)`) найден минимум в ~30 других flag-групп по всему приложению (`bnul, bnnl, bnpk, bnrg, bmyf, bnzp` и т.д.) — Phenotype используется массово, не только в setup.

Firebase Remote Config не обнаружен. Явного пакета `com.google.android.libraries.phenotype` как имени нет (переименован обфускатором), но лог-тег `"PhenotypeFlag"` и структура wrapper'а однозначно указывают на Phenotype.

---

## 8. Проверки модели устройства — сводка

См. п. 5. Итог: модель распознаётся через жёстко зашитую таблицу кодов (`akdv`), поддержка модели для setup — гибрид хардкод-флага и Phenotype allow/denylist (`ahtq.ad()`), оба контура **client-side** и не требуют обязательного сетевого похода в момент setup-сессии.

---

## Что не найдено / ограничения

- Явного `/setup/finish_setup` как отдельного endpoint'а нет — в этой версии заменён объединённым `smart_home/actions/setup`.
- `/setup/set_locale` отдельным литералом не найден — вероятно, поглощён `set_eureka_info` (поле `locale`/`i18n_info`).
- Явных `.proto`-ресурсов и человекочитаемых имён protobuf-полей нет — сопоставление имён облачных RPC-классов сделано косвенно, по контексту использования, а не по FileDescriptor.
- Полная цепочка вызовов от `NestPairingActivity`/`QrScanSetupActivity` до `aikc`/`ajjx` не прослежена до конца (глубокая generic ViewModel/Fragment-инфраструктура) — при необходимости можно продолжить прицельно по одному сценарию (например, только "добавление колонки через QR/BLE").
- Клиентская проверка версии прошивки колонки — не найдена.
- `homeplatformmesh-pa.googleapis.com` и ряд других googleapis-хостов не привязаны к конкретным вызовам в setup-пакетах — вероятно, пост-setup функциональность (Matter mesh commissioning).

---

## Артефакты анализа (локально, для дальнейшего копания)

- Декомпилированные Java-исходники (jadx): `/private/tmp/claude-501/-Users-ieffai-code-home-ru/aea406e2-896e-40bc-a133-6f8ba5e990de/scratchpad/gh/jadx-out/sources`
- Ресурсы/манифест (apktool): `/private/tmp/claude-501/-Users-ieffai-code-home-ru/aea406e2-896e-40bc-a133-6f8ba5e990de/scratchpad/gh/apktool-out`
- Распакованные сплиты APK: `/private/tmp/claude-501/-Users-ieffai-code-home-ru/aea406e2-896e-40bc-a133-6f8ba5e990de/scratchpad/gh/splits` (base.apk, config.ru.apk)

Эти файлы лежат во временном scratchpad-каталоге сессии и могут быть удалены после завершения сессии — при необходимости держать их дольше, стоит скопировать в постоянное место.
