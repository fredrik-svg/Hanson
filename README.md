
# Swedish ElevenLabs Voice Assistant on Raspberry Pi 5 (ReSpeaker USB Mic Array)

This project is a Swedish voice assistant running on a Raspberry Pi 5 using:

- [ElevenLabs Agents Platform](https://elevenlabs.io/docs/agents-platform)
- Seeed Studio **ReSpeaker USB Mic Array** (USB, not HAT)
- A Bluetooth speaker for audio output
- The built‑in **pixel_ring** LED on the ReSpeaker to indicate assistant status

Hotword detection is done locally on the Pi using **EfficientWord-Net** ("Hey Eleven").
Once the hotword is detected, a streaming conversation is started with an ElevenLabs
agent configured to speak Swedish.

## Hardware

- Raspberry Pi 5 (2–8 GB)
- microSD card with Raspberry Pi OS (64‑bit)
- Seeed Studio ReSpeaker USB Mic Array
- Bluetooth speaker paired with Raspberry Pi

> **OS-version att välja?**
> För hotword‑motorn (EfficientWord-Net) är det bäst att stanna på den
> ordinarie Raspberry Pi OS **Bookworm 64‑bit** som levereras med Python 3.11.
> Nyare test/"advanced" builds som hoppar till Python 3.12 gör att hotword
> paketet inte kan installeras. Använd alltså Bookworm (inte de senaste
> preview‑bilderna) så fungerar installationen som beskrivet nedan. På Python
> 3.12+ startar skriptet fortfarande, men hotword‑detektering stängs av och du
> får starta en session genom att trycka **Enter** i terminalen.

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

   > **Note:** EfficientWord-Net only supports Python versions below 3.12 and
   > requires `numpy==1.22.0`. When running on newer Python versions, the
   > hotword package is skipped and a modern `numpy` is installed instead so
   > that the rest of the environment can be set up without build failures.
   > To use hotword detection, run the project with Python 3.11 (or older)
   > where EfficientWord-Net can be installed.

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

## Hotword reference

This project expects a hotword reference file at:

```text
hotword_refs/hey_eleven_ref.json
```

Follow the ElevenLabs Raspberry Pi / EfficientWord-Net guide to record and
generate this reference JSON for the hotword `hey_eleven` (or change the code
and file name if you use another hotword).

## Running

From the project folder on your Pi:

```bash
source .venv/bin/activate
python hotword.py
```

The assistant will listen for the hotword:

- When you say **"Hey Eleven"**, the hotword detector will trigger.
- The conversation with the ElevenLabs agent starts.
- The ReSpeaker **pixel ring** shows different patterns when listening,
  thinking and speaking.
- When the conversation ends, the mic stream is reset so you can wake
  the assistant again.

## Notes

- The code and comments are mostly in Swedish since the target use‑case is a
  Swedish voice assistant. Feel free to adapt prompts, dynamic variables and
  callbacks for your own use.
- The USB Mic Array is used as a normal USB audio input; no `seeed-voicecard`
  kernel driver is required.
