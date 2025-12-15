# Debian Trixie (Debian 13) och Raspberry Pi 5 Kompatibilitet

Detta dokument beskriver de ändringar som gjorts för att stödja Debian GNU/Linux 13 (Trixie) på Raspberry Pi 5.

## Översikt

Debian Trixie introducerar två stora förändringar som påverkar detta projekt:

1. **Ljudsystem**: PipeWire är nu standardljudserver istället för direkt ALSA-åtkomst
2. **GPIO-hantering**: Raspberry Pi 5 har en ny RP1 I/O-kontroller som kräver libgpiod istället av RPi.GPIO

## Ljudsystem: PipeWire

### Vad har ändrats?

Debian Trixie använder **PipeWire** som standardljudserver för alla skrivbordsmiljöer. PipeWire ersätter både PulseAudio och JACK och ger:

- Enhetlig hantering av konsument- och professionellt ljud
- Dynamiskt justerbar latens
- Flexibel routing mellan ljudenheter
- Bättre stöd för Bluetooth-enheter

### Hur påverkar det projektet?

**Bra nyheter**: PyAudio och ALSA-verktyg fungerar fortfarande! 

- ALSA finns kvar som kernel-drivrutinsramverk
- `pipewire-alsa`-paketet tillhandahåller en ALSA-plugin som automatiskt routar ljud genom PipeWire
- Befintlig kod fungerar utan ändringar

### Installation

För att säkerställa att allt fungerar på Debian Trixie:

```bash
sudo apt-get install pipewire-alsa
```

### Ljudkonfiguration

På Debian Trixie, använd `wpctl` för att hantera ljudenheter:

```bash
# Lista tillgängliga enheter
wpctl status

# Sätt standardutgång
wpctl set-default <node-id>

# Justera volym
wpctl set-volume @DEFAULT_AUDIO_SINK@ 50%
```

För Bluetooth-högtalare:

```bash
# Para enhet
bluetoothctl
> scan on
> pair <MAC-adress>
> connect <MAC-adress>
> exit

# Sätt som standard
wpctl set-default <node-id>
```

### Felsökning

**Problem: PyAudio hittar ingen enhet**

```bash
# Installera PipeWire ALSA-plugin
sudo apt-get install pipewire-alsa

# Starta om PipeWire
systemctl --user restart pipewire
```

**Problem: Inget ljud hörs**

```bash
# Kontrollera att PipeWire körs
systemctl --user status pipewire

# Lista tillgängliga enheter
wpctl status

# Testa ljudutgång
speaker-test -t wav -c 2
```

**Problem: PipeWire RTKit-varningar**

Om du ser varningar som:
```
mod.rt: RTKit error: org.freedesktop.DBus.Error...
mod.rt: RTKit does not give us MaxRealtimePriority
```

Detta är vanligt och normalt inte problematiskt:
- **Vad det betyder:** PipeWire kunde inte få realtidsprioritet från RTKit
- **Påverkan:** Ljudet fungerar fortfarande, men med något högre latens
- **Orsak:** RTKit är inte installerat eller användaren saknar behörighet för realtidsprioritet
- **Lösning (valfritt):** 
  ```bash
  sudo apt-get install rtkit
  systemctl --user restart pipewire
  ```
- **Alternativ:** Ignorera varningarna om ljudprestandan är acceptabel

## GPIO-hantering: libgpiod

### Vad har ändrats?

Raspberry Pi 5 har en ny RP1 I/O-kontroller som gör RPi.GPIO inkompatibel. Istället måste vi använda **libgpiod**, vilket är den moderna Linux-standarden för GPIO-åtkomst.

### Huvudsakliga skillnader

| Aspekt | RPi.GPIO (Pi 1-4) | libgpiod (Pi 5) |
|--------|-------------------|-----------------|
| Enhetsåtkomst | `/dev/gpiomem` | `/dev/gpiochip4` |
| API | RPi.GPIO-specifik | Linux-standard |
| Kompatibilitet | Endast Raspberry Pi | Alla Linux-system |
| Python-paket | `RPi.GPIO` | `gpiod` / `python3-gpiod` |

### Hur projektet anpassats

Projektet detekterar automatiskt vilket GPIO-bibliotek som är tillgängligt:

1. **Försöker först gpiod** (för Pi 5 / Trixie)
2. **Faller tillbaka på RPi.GPIO** om gpiod inte finns
3. **Kör i manuellt läge** om inget GPIO-bibliotek finns

Koden stöder båda backends transparent utan att användaren behöver ändra något.

### Installation

**Rekommenderad metod (fungerar alltid):**

GPIO-stöd installeras automatiskt via `requirements.txt` som inkluderar Python-paketet `gpiod`:

```bash
pip install -r requirements.txt
```

**Alternativ metod (systempaket):**

Om du föredrar att använda systemversionen av libgpiod kan du försöka installera den:

```bash
sudo apt-get install python3-gpiod
```

**Obs:** Om kommandot ovan ger felet "Unable to locate package python3-gpiod", använd istället Python-paketet från PyPI (rekommenderad metod ovan). Båda metoderna fungerar lika bra.

**För äldre Pi-modeller:**

RPi.GPIO installeras också automatiskt via requirements.txt, eller kan installeras manuellt:

```bash
pip install RPi.GPIO
```

### Behörigheter

Udev-reglerna har uppdaterats för att stödja både RPi.GPIO och libgpiod:

```bash
# Lägg till användare i gpio-gruppen
sudo usermod -a -G gpio $USER

# Installera udev-regler
sudo cp 99-gpio.rules /etc/udev/rules.d/

# Ladda om regler
sudo udevadm control --reload-rules
sudo udevadm trigger

# Logga ut och in igen eller starta om
sudo reboot
```

### Kodexempel

Projektet hanterar båda backends internt, men här är hur de skiljer sig:

**RPi.GPIO (äldre Pi-modeller):**
```python
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(17, GPIO.FALLING, callback=callback)
```

**libgpiod (Pi 5):**
```python
import gpiod

chip = gpiod.Chip('/dev/gpiochip4')
line = chip.get_line(17)
line.request(
    consumer='my-app',
    type=gpiod.LINE_REQ_EV_FALLING_EDGE,
    flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP
)
# Poll for events
if line.event_wait(nsec=100000000):
    event = line.event_read()
```

### Dynamisk chip-upptäckt

På Pi 5 är GPIO-headern vanligtvis `/dev/gpiochip4`, men detta kan variera. Projektet söker automatiskt efter tillgängliga chips:

```python
for chip_num in [4, 0, 1, 2, 3]:
    chip_path = f'/dev/gpiochip{chip_num}'
    if os.path.exists(chip_path):
        try:
            chip = gpiod.Chip(chip_path)
            # Använd denna chip
            break
        except OSError:
            continue
```

### Felsökning

**Problem: "Could not find accessible gpiochip device"**

```bash
# Kontrollera att gpiochip-enheter finns
ls -la /dev/gpiochip*

# Verifiera behörigheter
groups  # Ska inkludera 'gpio'

# Kontrollera att gpiod är installerat
python -c "import gpiod; print('gpiod OK')"

# Om inte installerat, installera via pip (rekommenderat):
pip install gpiod

# Alternativt, försök systemversionen (om tillgänglig):
sudo apt-get install python3-gpiod
# Obs: Om du får "Unable to locate package", använd pip-metoden ovan istället

# Ladda om udev-regler
sudo udevadm control --reload-rules
sudo udevadm trigger
```

**Problem: "Permission denied" på /dev/gpiochip4**

```bash
# Kontrollera behörigheter
ls -la /dev/gpiochip4

# Ska visa något liknande:
# crw-rw---- 1 root gpio 254, 4 ... /dev/gpiochip4

# Om inte, installera udev-reglerna igen
sudo cp 99-gpio.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Automatisk detektering

Projektet visar vilket backend som används vid start:

```
Using GPIO backend: gpiod
Using GPIO LED if configured; otherwise running without light.
Running as non-root user in gpio group (recommended setup).
Button on /dev/gpiochip4 GPIO 17 initialized (pull-up). Starting state: released.
```

## Kompatibilitet

Projektet är nu kompatibelt med:

- ✅ Raspberry Pi 1-4 med Raspberry Pi OS Bookworm (RPi.GPIO)
- ✅ Raspberry Pi 5 med Raspberry Pi OS Bookworm (libgpiod)
- ✅ Raspberry Pi 5 med Debian 13 Trixie (libgpiod + PipeWire)
- ✅ Andra Linux-system utan GPIO (manuellt läge)

## Referenser

- [Debian PipeWire Wiki](https://wiki.debian.org/PipeWire)
- [libgpiod projekt](https://git.kernel.org/pub/scm/libs/libgpiod/libgpiod.git/)
- [Raspberry Pi GPIO dokumentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio-and-the-40-pin-header)
- [Python gpiod bindings](https://pypi.org/project/gpiod/)

## Sammanfattning

Projektet stöder nu fullt ut Debian Trixie på Raspberry Pi 5 genom:

1. **PipeWire-kompatibilitet**: PyAudio fungerar genom pipewire-alsa-pluginen
2. **libgpiod-stöd**: Automatisk detektering och användning av modernt GPIO-bibliotek
3. **Bakåtkompatibilitet**: Fungerar fortfarande på äldre Pi-modeller med RPi.GPIO
4. **Transparens**: Användaren behöver inte göra några kodändringar

Alla ändringar är testade och validerade för både gamla och nya system.
