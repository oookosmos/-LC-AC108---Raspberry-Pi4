# Установка: Raspberry Pi 4 + LC-AC108 + Vosk

## 1. Проверенная конфигурация

| Компонент | Значение |
|---|---|
| Плата | Raspberry Pi 4, 2 GB RAM |
| ОС | Raspberry Pi OS 64-bit, Debian 13 Trixie |
| Ядро на момент сборки | `6.18.60+rpt-rpi-v8` |
| Python | `3.13.5` |
| Аудиоплата | LC-Tech RPI_AC108, AC108, 4 MEMS |
| I2C | шина 1, адрес AC108 `0x3b` |
| ALSA capture | 4 канала, `S32_LE`, 16000 Hz |
| ASR | Vosk + `vosk-model-small-ru-0.22` |
| Выход звука для теста | HDMI, `plughw:0,0` на проверенной системе |

> Номер ядра и номера ALSA-карт могут изменяться после обновления ОС или загрузки. Не используйте приведённые номера как универсальные.

## 2. Подготовка системы

Обновите ОС и установите инструменты:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y git build-essential dkms i2c-tools alsa-utils sox python3-venv python3-pip
sudo reboot
```

После загрузки проверьте систему:

```bash
uname -a
uname -m
python3 --version
```

Для этой конфигурации архитектура должна быть `aarch64`.

## 3. I2C и проверка AC108

Включите I2C через `sudo raspi-config` → Interface Options → I2C, затем перезагрузите Pi.

Проверьте наличие устройств:

```bash
ls -l /dev/i2c-*
sudo i2cdetect -y 1
```

В проверенной конфигурации AC108 отвечал по адресу `0x3b` на шине 1. Если адрес не обнаружен, проверьте питание платы, посадку GPIO-разъёма и включение I2C.

## 4. Получение и сборка драйвера

Использовался репозиторий:

```text
https://github.com/avisual/seeed-voicecard.git
```

Рабочая ветка на момент настройки: `pi5`. Несмотря на название ветки, она содержала совместимые изменения для ядра 6.18 и была собрана на Raspberry Pi 4. Это не означает, что ветка официально поддерживает любую конфигурацию Pi 4.

Клонирование:

```bash
git clone -b pi5 https://github.com/avisual/seeed-voicecard.git ~/seeed-voicecard-618-test
cd ~/seeed-voicecard-618-test
```

Проверьте наличие заголовков именно для запущенного ядра:

```bash
uname -r
ls -ld /lib/modules/$(uname -r)/build
```

В проверенной системе каталог ссылался на:

```text
/usr/src/linux-headers-6.18.60+rpt-rpi-v8
```

Затем выполните предусмотренную репозиторием сборку. Конкретные команды сборки могут меняться между ревизиями; сначала изучите `README` и Makefile текущего checkout:

```bash
cd ~/seeed-voicecard-618-test
ls
sed -n '1,240p' README.md
```

В ходе этой настройки успешно собраны модули:

- `snd-soc-ac108.ko`
- `snd-soc-seeed-voicecard.ko`
- `snd-soc-wm8960.ko` (для данной платы не требуется)

Устанавливались только необходимые AC108 и Seeed voicecard модули:

```bash
sudo install -D -m 0644 snd-soc-ac108.ko /lib/modules/$(uname -r)/extra/snd-soc-ac108.ko
sudo install -D -m 0644 snd-soc-seeed-voicecard.ko /lib/modules/$(uname -r)/extra/snd-soc-seeed-voicecard.ko
sudo depmod -a
```

**Важно:** команды выше предполагают, что файлы `.ko` находятся в текущем каталоге. Путь к результатам сборки может отличаться. Не используйте готовые бинарные `.ko` от другого ядра. Проверяйте `modinfo` и `vermagic`:

```bash
modinfo snd-soc-ac108 | grep -E 'filename|vermagic'
modinfo snd-soc-seeed-voicecard | grep -E 'filename|vermagic'
```

`vermagic` должен соответствовать текущему ядру.

## 5. Device Tree overlay

Для платы использовался пользовательский overlay на основе `seeed-4mic-voicecard-overlay.dts` из `seeed-voicecard`.

В нём изменено имя звуковой карты на `lc-ac108-4mic`; остальная конфигурация оставлена близкой к исходному overlay:

- `compatible = "brcm,bcm2708"`;
- AC108 на I2C1, адрес `0x3b`, compatible `"x-power,ac108_0"`;
- I2S формат `dsp_a`;
- частота системного тактирования 24 MHz;
- capture channels override 4;
- TDM slots = 2, slot width = 32;
- masks `<1 1 0 0>`.

Оригинальный DTS и точные команды компиляции зависят от ревизии upstream. Скопируйте исходный overlay из клонированного репозитория и проверьте его перед модификацией. В рабочей системе собранный файл назывался `lc-ac108-4mic-test.dtbo`.

Установка overlay:

```bash
sudo install -m 0644 lc-ac108-4mic-test.dtbo /boot/firmware/overlays/lc-ac108-4mic-test.dtbo
```

В `/boot/firmware/config.txt` добавлена строка:

```ini
dtoverlay=lc-ac108-4mic-test
```

Для автозагрузки модулей создан файл `/etc/modules-load.d/ac108.conf`:

```text
snd-soc-ac108
snd-soc-seeed-voicecard
```

После этого:

```bash
sudo depmod -a
sudo reboot
```

При диагностике проверьте:

```bash
lsmod | grep -E 'ac108|seeed_voicecard'
dmesg | grep -iE 'ac108|seeed|i2s'
cat /proc/asound/cards
arecord -l
```

Ожидается карта с именем `lc-ac108-4mic` и устройством захвата `bcm2835-i2s-ac10x-codec0`.

## 6. Настройка усиления микрофонов

В проверенной системе PGA gain каналов ADC1–ADC4 был установлен в 20 (шаг регулировки — 1 dB). Уровни сохранились после перезагрузки.

Найдите актуальный номер карты:

```bash
arecord -l
```

Затем замените `2` в командах ниже на свой номер:

```bash
for ch in 1 2 3 4; do
  amixer -c 2 cset name="ADC${ch} PGA gain" 20
done
```

Проверьте значения:

```bash
amixer -c 2 contents | grep -A4 'PGA gain'
```

Не копируйте усиление вслепую для другого экземпляра платы или микрофонов: подберите уровень так, чтобы речь была разборчивой, но не было клиппинга.

## 7. Проверка записи 4 каналов

Определите номер карты через `arecord -l`. В проверенной системе после перезагрузки это была карта 2:

```bash
arecord -D hw:2,0 -f S32_LE -r 16000 -c 4 -d 10 ~/mic-test.wav
```

Проверьте формат:

```bash
soxi ~/mic-test.wav
```

Ожидалось: 4 канала, 16000 Hz, 32-bit signed PCM, длительность 10 секунд.

Преобразуйте запись в моно и послушайте:

```bash
sox ~/mic-test.wav -c 1 -b 16 -e signed-integer -r 16000 ~/mic-test-mono.wav remix -
```

Для воспроизведения на проверенном HDMI-выходе:

```bash
aplay -l
aplay -D plughw:0,0 ~/mic-test-mono.wav
```

HDMI-номер может отличаться на другой системе. Используйте `aplay -l`.

## 8. Установка Vosk

Создайте отдельную рабочую папку и виртуальное окружение:

```bash
mkdir -p ~/voice-assistant/models
cd ~/voice-assistant
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install vosk
```

Проверьте импорт:

```bash
python -c "import vosk; print('Vosk установлен успешно')"
```

Скачайте модель `vosk-model-small-ru-0.22` со страницы модели Vosk и распакуйте так, чтобы существовал путь:

```text
~/voice-assistant/models/vosk-model-small-ru-0.22
```

Модель намеренно не хранится в Git: это отдельный крупный бинарный ресурс. Проверьте, что каталог содержит файлы модели, например `am`, `conf`, `graph`, `ivector`.

## 9. Проверка Vosk на тестовой записи

После создания 4-канальной записи преобразуйте её в моно:

```bash
sox ~/mic-test.wav -c 1 -b 16 -e signed-integer -r 16000 ~/mic-test-mono.wav remix -
```

Создайте `~/voice-assistant/test_vosk.py`:

```python
import json
import wave
from pathlib import Path
from vosk import Model, KaldiRecognizer

BASE_DIR = Path.home() / "voice-assistant"
MODEL_DIR = BASE_DIR / "models" / "vosk-model-small-ru-0.22"
AUDIO_FILE = Path.home() / "mic-test-mono.wav"

model = Model(str(MODEL_DIR))
with wave.open(str(AUDIO_FILE), "rb") as wf:
    rec = KaldiRecognizer(model, wf.getframerate())
    print("Распознавание началось...")
    while True:
        data = wf.readframes(4000)
        if not data:
            break
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            if result.get("text"):
                print(result["text"])
    result = json.loads(rec.FinalResult())
    print("Итог:", result.get("text", ""))
```

Запуск:

```bash
cd ~/voice-assistant
source venv/bin/activate
python test_vosk.py
```

## 10. Потоковое распознавание в реальном времени

В корне рабочей папки создайте `live_vosk.py` с кодом из [`../scripts/live_vosk.py`](../scripts/live_vosk.py) (или скопируйте файл в `~/voice-assistant/live_vosk.py`). В скрипте используется ALSA-идентификатор `hw:CARD=lcac1084mic,DEV=0`.

Проверьте идентификатор карты:

```bash
arecord -l
arecord -L | grep -A2 -B2 lcac1084mic
```

Запуск:

```bash
cd ~/voice-assistant
source venv/bin/activate
python live_vosk.py
```

Ожидаемое поведение: после загрузки модели появляется `Микрофоны запущены`; после произнесённой фразы и паузы программа выводит `Распознано: ...`. Остановка — `Ctrl+C`.

Если ALSA не находит `CARD=lcac1084mic`, проверьте фактический ID:

```bash
cat /proc/asound/cards
```

и скорректируйте `ALSA_DEVICE` в скрипте. Не ориентируйтесь только на номер карты: он может изменяться.
