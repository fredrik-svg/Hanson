
import importlib.util
import os
import signal
import time

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import (
    Conversation,
    ConversationInitiationData,
)
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface


load_dotenv()

BUTTON_PIN = 17

GPIO_AVAILABLE = importlib.util.find_spec("RPi.GPIO") is not None

status_led_pin_env = os.getenv("STATUS_LED_PIN")
try:
    STATUS_LED_PIN = int(status_led_pin_env) if status_led_pin_env else None
except ValueError:
    print(
        "Invalid value for STATUS_LED_PIN – provide a GPIO number, e.g. 27. "
        "Ignoring LED configuration."
    )
    STATUS_LED_PIN = None

STATUS_LED_ACTIVE_HIGH = os.getenv("STATUS_LED_ACTIVE_HIGH", "1") != "0"

if GPIO_AVAILABLE:
    import RPi.GPIO as GPIO

agent_id = os.getenv("ELEVENLABS_AGENT_ID")
api_key = os.getenv("ELEVENLABS_API_KEY")

if not agent_id:
    raise RuntimeError("ELEVENLABS_AGENT_ID is not set in the environment")
if not api_key:
    raise RuntimeError("ELEVENLABS_API_KEY is not set in the environment")

elevenlabs = ElevenLabs(api_key=api_key)

# Dynamic variables that can be used in your agent prompt
dynamic_vars = {
    "user_name": "Fredrik",
    "greeting": "Hej",
    "language": "svenska",
}

config = ConversationInitiationData(dynamic_variables=dynamic_vars)

STATUS_LED_INITIALIZED = False


def setup_status_led():
    """Initialize status LED via GPIO if a pin is provided."""

    global STATUS_LED_INITIALIZED

    if not GPIO_AVAILABLE or STATUS_LED_PIN is None:
        return

    try:
        GPIO.setup(
            STATUS_LED_PIN,
            GPIO.OUT,
            initial=GPIO.LOW if STATUS_LED_ACTIVE_HIGH else GPIO.HIGH,
        )
        STATUS_LED_INITIALIZED = True
        print(
            f"Status-LED styrs via GPIO {STATUS_LED_PIN} (aktiveras med "
            f"{'HIGH' if STATUS_LED_ACTIVE_HIGH else 'LOW'})."
        )
    except RuntimeError as e:
        print(
            "Kunde inte initiera status-LED via GPIO. Kontrollera att skriptet "
            "körs med root-behörighet och att pinnen inte används av något "
            "annat."
        )
        print(f"Detaljer: {e}")


def set_status_led(active: bool):
    """Turn status LED on/off if initialized."""

    if not STATUS_LED_INITIALIZED:
        return

    level = GPIO.HIGH if (active == STATUS_LED_ACTIVE_HIGH) else GPIO.LOW
    try:
        GPIO.output(STATUS_LED_PIN, level)
    except RuntimeError as e:
        print(f"Kunde inte styra status-LED: {e}")


def ring_idle():
    """LED off (idle state)."""
    set_status_led(False)


def ring_listening():
    """LED indicates the assistant is awake and ready to listen."""
    set_status_led(True)


def ring_thinking():
    """LED indicates the agent is thinking/processing."""
    set_status_led(True)


def ring_speaking():
    """LED indicates the agent is speaking."""
    set_status_led(True)


def create_conversation():
    """Create a new ElevenLabs conversation."""

    def on_agent_response(response: str):
        print(f"Agent: {response}")
        ring_speaking()

    def on_agent_response_correction(original: str, corrected: str):
        print(f"Agent: {original} -> {corrected}")
        ring_speaking()

    def on_user_transcript(transcript: str):
        print(f"Du: {transcript}")
        ring_thinking()

    return Conversation(
        elevenlabs,
        agent_id,
        config=config,
        requires_auth=bool(api_key),
        audio_interface=DefaultAudioInterface(),
        callback_agent_response=on_agent_response,
        callback_agent_response_correction=on_agent_response_correction,
        callback_user_transcript=on_user_transcript,
    )


def start_conversation_flow():
    """Start an ElevenLabs session and handle cleanup."""

    print("Startar ElevenLabs-session...")
    ring_listening()

    try:
        conversation = create_conversation()
        conversation.start_session()

        def signal_handler(sig, frame):
            print("Avbryter session...")
            try:
                conversation.end_session()
            except Exception as e:
                print(f"Fel vid avslut av session: {e}")

        signal.signal(signal.SIGINT, signal_handler)

        conversation_id = conversation.wait_for_session_end()
        print(f"Samtals-ID: {conversation_id}")

    except Exception as e:
        error_text = str(e)
        print(f"Fel under konversation: {error_text}")
        if "needs_authorization" in error_text or "authorization" in error_text:
            print(
                "Kontrollera att ELEVENLABS_API_KEY är korrekt satt och att "
                "nyckeln har behörighet för valt agent-ID."
            )
    finally:
        print("Session slut, städar upp...")
        ring_idle()
        time.sleep(1)


def manual_conversation_prompt():
    """Fallback mode when the GPIO button cannot be used."""

    print(
        "RPi.GPIO saknas eller kan inte användas. Tryck Enter för att starta "
        "en konversation manuellt."
    )
    try:
        while True:
            input("\nStarta ny session (Enter): ")
            start_conversation_flow()
    except KeyboardInterrupt:
        print("Avslutar via CTRL+C...")
    finally:
        ring_idle()


def setup_button() -> bool:
    """Configure the GPIO button and provide helpful debug info."""

    try:
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    except RuntimeError as e:
        print("Kunde inte konfigurera knappen via GPIO.")
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            print("RPi.GPIO kräver root-behörighet. Kör skriptet med sudo.")
        print(f"Detaljer: {e}")
        return False

    initial_state = GPIO.input(BUTTON_PIN)
    print(
        f"Knapp på GPIO {BUTTON_PIN} initierad (pull-up). Startläge: "
        f"{'NEDTRYCKT' if initial_state == GPIO.LOW else 'uppläppt'}."
    )
    return True


def main():
    ring_idle()

    if not GPIO_AVAILABLE:
        manual_conversation_prompt()
        return

    try:
        print("Using GPIO LED if configured; otherwise running without light.")

        if hasattr(os, "geteuid") and os.geteuid() != 0:
            print("Varning: RPi.GPIO svarar normalt bara för root. Kör med sudo.")

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        setup_status_led()

        if not setup_button():
            manual_conversation_prompt()
            return

        print(
            "Hotword-stöd är borttaget. Tryck på knappen mellan GPIO 17 och "
            "GND för att starta en konversation (CTRL+C för att avsluta)."
        )

        while True:
            try:
                channel = GPIO.wait_for_edge(
                    BUTTON_PIN, GPIO.FALLING, bouncetime=300, timeout=10000
                )
            except RuntimeError as e:
                print(
                    "Kunde inte lyssna på knappen via GPIO. Växlar till "
                    "manuellt läge."
                )
                print(f"Detaljer: {e}")
                manual_conversation_prompt()
                return

            if channel is None:
                print("Ingen knapptryckning upptäcktes på 10 sekunder...")
                continue

            start_conversation_flow()
    except KeyboardInterrupt:
        print("Avslutar via CTRL+C...")
    finally:
        ring_idle()
        if GPIO_AVAILABLE:
            GPIO.cleanup()


if __name__ == "__main__":
    main()
