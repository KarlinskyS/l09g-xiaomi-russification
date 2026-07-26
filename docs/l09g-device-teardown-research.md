Исследование Xiaomi Mi Sm

Собрал данные из независиветка OpenWrt-форума (2страницы), проект duhow/xiaoai-patch, статья Hackaday/Dennis Giese. Важная
оговорка сразу: полный roе получен никем (последнеепредметное обновление — апрель 2023). Дальше — по пунктам.

Железо / SoC

- Amlogic AXG-семейство (board id axg_s420_v1_gva), ARM Cortex-A53, Hardware
  name: Amlogic (DT) — похо
- Флеш: 2GB NAND, Toshiba TC58NVG1S3HBAI4, UBI-файловая система поверх MTD.
- Wi-Fi: RTL8821CS (SDIO)
- Ядро: Linux 4.9.113 (Android-модифицированный).

Boot / U-Boot

- Бутлоадер: U-Boot 2015.01-gfe79c6daed-dirty (Aug 27 2020), доступен полный
  набор команд — nand, mmc, mtdparts, ubi info,clkmsr.
- Ключевые env-переменныеux=enforcing,factory_mode=0, active_slot=normal.
- bootdelay=1 — то самое о успеть прервать загрузкус UART.

Partition layout (MTD/NAND)

bootloader : 0x000000000000–0x000000200000
tpl : 0x0000008000
recovery : 0x000001000000–0x000001a00000
boot : 0x000001a000
system : 0x000002600000–0x000003600000
chrome : 0x0000036000
factory : 0x000007a00000–0x000007e00000
data : 0x000007e000
Раздел chrome (самый большой) — почти наверняка Chromecast/Cast-стек Google.

UART

- 3-контактный разъём на плате: RX (зелёный), GND (чёрный), TX (белый), 115200
  baud, TTL-адаптер (PL2303
- Даёт консоль U-Boot и лог загрузки Android. Дамп прошивки делался буквально
  через md.b 0x0 0x10000000отом конвертация в бинарник (uboot_mdb_to_image.py, binwalk, abootimg).

ADB / root

- В логе загрузки встречается строка "enable adb debug prop" — то есть механизм включения adb в
- Но по факту рабочего adb/shell после загрузки никто не получил — Androidboots только в user-режим
  Recovery / factory mode / - Раздел recovery присутс
- factory_mode=0 в U-Boot env — это выключенный производственный тестовый режим. У других Xiaomi/Amtory mode на этапе QCавтоматически открывает adb/root — на L09G это не проверено, но выглядит самый перспективный векто
- fastboot — команда есть в самом U-Boot (Amlogic-реализация, не "стандарAndroid fastboot), пригодлов при физическомдоступе.  
  OTA / прошивка
- Общий контекст по линейке Xiaomi (Dennis Giese, Hackaday 2019): часть иWiFi-колонок исторически по HTTP — отсюдаклассический MITM-путь (DNS-спуфинг апдейт-сервера + подсунутый .img). - Для L09G это не подтверAndroid-база, вероятнееHTTPS с проверкой — то есть тот же трюк, скорее всего, тут не сработает ттривиально, как на старых
  Сетевые интерфейсы (nmap
  8008 http — Ca Chromecast)
  8009 ssl/ajp13 — Cast v2 control TLS (стандартный Chromecast) 8443 https-alt — вt/Home API
  9000 ssl/cslistener — нестандартный, не идентифицирован 10001 ssl/scp-config — нIO (miIO обычно UDP/54321); похоже на проприетарный конфиг-сервис  
  Chromecast / Google Assistant
- Порты 8008/8009 = штатный Google Cast SDK, зашитый вендором "как есть" не Xiaomi-самопал, а лицеаздел chrome в NAND).
- Google Assistant — тоже, по всей видимости, референсная сборка Google дпартнёрских "Google Assisалогично JBL Link, LenovoSmart Clock), со своим hotword/VAD и HTTPS/gRPC до Google. - Готового публичного анаа/пиннинга для L09G нет —это открытый вопрос.  
  Прямой ответ на твой вопрос — запасной путь, если MITM перестанет работат
  Честно: готового рабочего софтового fallback для этой конкретной модели нсуществует — комьюнити заивой root/shell послезагрузки Android никто не получил. Поэтому:

1. UART + U-Boot — единственный проверенный fallback, не зависящий от сетпереживёт любые изменения(закрытие сертификатногопиннинга, смену DNS-инфраструктуры, отзыв учёток) просто потому, что это физический доступ к железка. Но сейчас это даёттолько: дамп/запись разделов через nand/mmc, правку env-переменных, прерываниеboot — не даёт готового ш
2. Дальше это направление реалистично развивать так, как это делает duhow/xiaoai-patch для по, L09A/B и т.д.): дампboot/recovery, патч default.prop/ro.secure/ro.debuggable в извлечённом image, запись патченного образа L09G это не готовый рецепт, а R&D-работа с нуля — партиции и точки записи уже задокументированы (см. layout выше), это существ
3. Стоит проверить factory_mode=1 через U-Boot env — по аналогии с другими Xiaomi-устройствами это мt на этапе загрузки. Никемне протестировано публично — кандидат №1 для быстрой проверки.
4. Сетевой fallback (спуф старых XiaoAI-колонок) —вероятен только если OTA-канал реально unsigned/HTTP, что для этой Android+SELinux-enforcingолагайся на него безпредварительной проверки трафика обновления.

Итого: держи UART как страховку на случай обрыва MITM, но закладывай, что это сейчас "аварийный люк", а канал управления — до него ещё нужно дописать недостающий кусок (boot/recovery патч), которого в паблике под L09G нет.
Источники:

- XDA: How to get access to Xiaomi MI Smart Speaker L09G (https://xdaforums.com/t/how-to-get-access-to-del-l09g.4408293/)
- OpenWrt forum: Adding OpenWrt support for L09G (https://forum.openwrt.org/t/adding-openwrt-support-fomodel-l09g/121216)
- https://github.com/duhow/xiaoai-patch и Discussion #46 (L09G) (https://github.com/duhow46)
- Hackaday: Reverse-Engineering Xiaomi IoT Firmware (Dennis Giese) (https://hackaday.com/201g-xiaomi-iot-firmware/)
- FCC ID 2AFZZL09G internal photos/manual (https://fccid.io/2AFZZL0l-Photos-5399785)
