# Cast getUserMedia probe for L09G

Read-only диагностика: запускает Custom Receiver на **одной** простой колонке
и снимает четыре ответа (есть ли receiver, `mediaDevices`, `getUserMedia`,
реальный сигнал с микрофонов). Громкость не меняет, после пробы шлёт `STOP`.

Пока нет App ID из Cast Developer Console и публичного HTTPS с валидным
сертификатом, запускать нечего: колонка забирает URL приёмника у Google по
App ID, sender URL не подставляет.

Целевая колонка по умолчанию — Ванная `192.168.1.118`. Кухню `192.168.1.209`
скрипт отказывается трогать (приветствия Network Guardian).

## Запуск с NAS

Mac в корпоративной Wi‑Fi до домашних колонок не достаёт. На хосте NAS нет
`python3` — нужен контейнер `hermes-netguard` и флаг `-i`, иначе heredoc
съедается.

1. Выложить `receiver.html` на HTTPS с нормальным сертификатом.
2. Зарегистрировать unpublished Custom Receiver, Receiver URL = этот HTML,
   namespace `urn:x-cast:hermes.micprobe`.
3. Скопировать `sender.py` в контейнер или смонтировать репозиторий и:

```
CAST_APP_ID=XXXX CAST_SPEAKER_IP=192.168.1.118 \
  docker exec -i hermes-netguard python3 - < tools/cast-mic-probe/sender.py
```

Либо положить файл внутрь контейнера рядом с `/app/cast.py`.

Зависимость: `cast.py` из скилла Network Guardian в репозитории `hermes`
(`skills/smart-home/network-guardian/scripts/agent/cast.py`). В контейнере он
уже лежит как `/app/cast.py`. `Session.wait()` возвращает payload, не конверт
сообщения — sender фильтрует `type == "probe"`.

Исследование и критерии успеха: [`docs/l09g-ssh-and-cast-mic-2026-11-09.md`](../../docs/l09g-ssh-and-cast-mic-2026-11-09.md).
