
# Swedish ElevenLabs Voice Assistant on Raspberry Pi 5 (ReSpeaker USB Mic Array)

This project is a Swedish voice assistant running on a Raspberry Pi 5 using:

- [ElevenLabs Agents Platform](https://elevenlabs.io/docs/agents-platform)
- Seeed Studio **ReSpeaker USB Mic Array** (USB, not HAT)
- A Bluetooth speaker for audio output
- The built‑in **pixel_ring** LED on the ReSpeaker to indicate assistant status
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

1. Clone this repo to your Pi:

   ```bash
   git clone <your-repo-url>.git
   cd <your-repo-folder>
   ```

2. Create and activate a Python virtualenv (recommended):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Make sure your ReSpeaker USB Mic Array is plugged in and recognized as
   a USB audio input device (`arecord -l` should list it).

5. Pair and set your Bluetooth speaker as the default output (via `bluetoothctl`
   and `wpctl` / `pavucontrol`). The ElevenLabs SDK will play audio to the
   default sink.

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

## Running

From the project folder on your Pi:

```bash
source .venv/bin/activate
python hotword.py
```

The assistant will wait for a button press on **GPIO 17** (wired to **GND**):

- Press the button to start a conversation with the ElevenLabs agent.
- The ReSpeaker **pixel ring** shows different patterns when listening,
  thinking and speaking.
- When the conversation ends, the script returns to waiting for the next
  button press.

> **GPIO-behörighet**
> `RPi.GPIO` kräver root. Om knappen inte reagerar – kör skriptet med `sudo`
> eller lägg till lämplig `udev`-regel.

## GPIO LED in place of the pixel ring

If you prefer a simple LED connected directly to the Raspberry Pi instead of
the ReSpeaker pixel ring, set these environment variables before running
`hotword.py`:

- `STATUS_LED_PIN` – GPIO number for the LED (e.g. `27`).
- `STATUS_LED_ACTIVE_HIGH` – set to `0` if your LED lights when driven LOW
  (default is `1`, i.e. active HIGH).
- `USE_PIXEL_RING=0` – optional; forces the pixel ring off even if available.

With `STATUS_LED_PIN` set, the script will drive that pin HIGH/LOW to show the
assistant state.

## Notes

- The code and comments are mostly in Swedish since the target use‑case is a
  Swedish voice assistant. Feel free to adapt prompts, dynamic variables and
  callbacks for your own use.
- The USB Mic Array is used as a normal USB audio input; no `seeed-voicecard`
  kernel driver is required.
