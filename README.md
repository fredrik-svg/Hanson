
# Swedish ElevenLabs Voice Assistant on Raspberry Pi 5 (ReSpeaker USB Mic Array)

This project is a Swedish voice assistant running on a Raspberry Pi 5 using:

- [ElevenLabs Agents Platform](https://elevenlabs.io/docs/agents-platform)
- Seeed Studio **ReSpeaker USB Mic Array** (USB, not HAT)
- A Bluetooth speaker for audio output
- A GPIO-driven LED to indicate assistant status
- A physical button between **GPIO 17** and **GND** that starts a conversation when
  pressed

## Hardware

- Raspberry Pi 5 (2–8 GB)
- microSD card with Raspberry Pi OS (64‑bit)
- Seeed Studio ReSpeaker USB Mic Array
- Bluetooth speaker paired with Raspberry Pi

> **OS-version att välja?**
> Rekommenderad version är fortfarande Raspberry Pi OS **Bookworm 64‑bit**.
> Projektet har tagit bort hotword‑motorn helt, så det fungerar även på
> Python 3.12+ utan att behöva den äldre EfficientWord‑Net‑beroenden.

## Setup

### SSH-inställning

För att konfigurera och köra projektet på din Raspberry Pi rekommenderas SSH-åtkomst:

1. **Aktivera SSH på Raspberry Pi:**

   Om du har tillgång till en skärm och tangentbord:
   ```bash
   sudo raspi-config
   ```
   Navigera till "Interface Options" → "SSH" → "Yes"

   Alternativt, aktivera SSH via terminalen:
   ```bash
   sudo systemctl enable ssh
   sudo systemctl start ssh
   ```

2. **Hitta Pi:ns IP-adress:**

   På Raspberry Pi:
   ```bash
   hostname -I
   ```

3. **Anslut från din dator:**

   ```bash
   ssh pi@<raspberry-pi-ip-address>
   ```
   
   Använd det lösenord du skapade vid första uppstarten av Raspberry Pi OS. Om du använder en äldre installation med standardlösenordet `raspberry`, bör du ändra det omedelbart:
   ```bash
   passwd
   ```

4. **[Valfritt] Konfigurera SSH-nyckelbaserad autentisering:**

   På din dator, generera ett SSH-nyckelpar (om du inte redan har ett):
   ```bash
   ssh-keygen -t ed25519
   ```

   Kopiera din publika nyckel till Pi:n:
   ```bash
   ssh-copy-id pi@<raspberry-pi-ip-address>
   ```

   Nu kan du ansluta utan lösenord.

### Installera projektet

1. Klona detta repository till din Pi:

   ```bash
   git clone <your-repo-url>.git
   cd <your-repo-folder>
   ```

2. Installera systempaket som krävs för PyAudio:

   ```bash
   sudo apt-get update
   sudo apt-get install -y portaudio19-dev
   ```

3. Skapa och aktivera en Python virtualenv (rekommenderat):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

4. Installera Python-beroenden:

   ```bash
   pip install -r requirements.txt
   ```

5. Säkerställ att din ReSpeaker USB Mic Array är inkopplad och känns igen
   som en USB-ljudingångsenhet (`arecord -l` bör visa den).

6. Para och ställ in din Bluetooth-högtalare som standardutgång (via
   `bluetoothctl` och `wpctl` / `pavucontrol`). ElevenLabs SDK kommer
   att spela upp ljud till standard sink.

## ElevenLabs configuration

1. Create an **Agent** in the ElevenLabs dashboard.
2. Configure the agent's voice and system prompt to respond in **Swedish**.
3. Copy the **Agent ID**.
4. Create an API key.

On the Pi, export these environment variables (or put them in an `.env` and load
them yourself):

```bash
export ELEVENLABS_API_KEY="your_api_key_here"
export ELEVENLABS_AGENT_ID="your_agent_id_here"
```

## GPIO-behörighet (GPIO Permissions)

`RPi.GPIO` kräver normalt root-behörighet för att komma åt GPIO-pinnarna. Det finns två alternativ:

> **För detaljerade instruktioner och felsökning, se [GPIO_PERMISSIONS.md](GPIO_PERMISSIONS.md)**

### Alternativ 1: Kör med sudo (snabbast men mindre säkert)

```bash
source .venv/bin/activate
sudo .venv/bin/python hotword.py
```

### Alternativ 2: Konfigurera udev-regel (rekommenderas)

För att köra skriptet utan `sudo` kan du installera en udev-regel som ger
åtkomst till GPIO för användare i gruppen `gpio`:

1. Lägg till din användare i `gpio`-gruppen:

   ```bash
   sudo usermod -a -G gpio $USER
   ```

2. Kopiera udev-regeln till systemet:

   ```bash
   sudo cp 99-gpio.rules /etc/udev/rules.d/
   ```

3. Ladda om udev-reglerna:

   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

4. Logga ut och logga in igen för att gruppmedlemskapet ska träda i kraft.

   Alternativt starta om Raspberry Pi:
   ```bash
   sudo reboot
   ```

5. Verifiera att du är medlem i `gpio`-gruppen:

   ```bash
   groups
   ```

   Du bör se `gpio` i listan.

## Running

From the project folder on your Pi:

```bash
source .venv/bin/activate
python hotword.py
```

The assistant will wait for a button press on **GPIO 17** (wired to **GND**):

- Press the button to start a conversation with the ElevenLabs agent.
- An LED connected to a GPIO pin can show status (listening/thinking/speaking).
- When the conversation ends, the script returns to waiting for the next
  button press.

## GPIO-LED

Set these variables before running `hotword.py`:

- `STATUS_LED_PIN` – GPIO number for the LED (e.g. `27`).
- `STATUS_LED_ACTIVE_HIGH` – set to `0` if your LED lights when driven LOW
  (default is `1`, i.e. active HIGH).
- `THINKING_BLINK_SECONDS` – optional blink duration (seconds) when entering
  the thinking state; set to `0` to disable the blink.

With `STATUS_LED_PIN` set, the script drives that pin HIGH/LOW to show the
assistant status. If the variable is omitted, the script runs without a status
light.

## Notes

- The code and comments are mostly in Swedish since the target use‑case is a
  Swedish voice assistant. Feel free to adapt prompts, dynamic variables and
  callbacks for your own use.
- The USB Mic Array is used as a normal USB audio input; no `seeed-voicecard`
  kernel driver is required.
