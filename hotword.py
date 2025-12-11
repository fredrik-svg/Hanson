
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
thinking_blink_env = os.getenv("THINKING_BLINK_SECONDS", "0.05")
try:
    THINKING_BLINK_SECONDS = float(thinking_blink_env)
except ValueError:
    THINKING_BLINK_SECONDS = 0.05

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
            f"Status LED controlled via GPIO {STATUS_LED_PIN} (active with "
            f"{'HIGH' if STATUS_LED_ACTIVE_HIGH else 'LOW'})."
        )
    except RuntimeError as e:
        print(
            "Could not initialize status LED via GPIO. Ensure the script runs "
            "with root privileges and that the pin is not used by anything else."
        )
        print(f"Details: {e}")


def set_status_led(active: bool):
    """Turn status LED on/off if initialized."""

    if not STATUS_LED_INITIALIZED:
        return

    level = GPIO.HIGH if (active == STATUS_LED_ACTIVE_HIGH) else GPIO.LOW
    try:
        GPIO.output(STATUS_LED_PIN, level)
    except RuntimeError as e:
        print(f"Could not control status LED: {e}")


def ring_idle():
    """LED off (idle state)."""
    set_status_led(False)


def ring_listening():
    """LED indicates the assistant is awake and ready to listen."""
    set_status_led(True)


def ring_thinking():
    """LED indicates the agent is thinking/processing."""
    if THINKING_BLINK_SECONDS > 0:
        set_status_led(False)
        time.sleep(THINKING_BLINK_SECONDS)
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
        print(f"You: {transcript}")
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

    print("Starting ElevenLabs session...")
    ring_listening()

    try:
        conversation = create_conversation()
        conversation.start_session()

        def signal_handler(sig, frame):
            print("Cancelling session...")
            try:
                conversation.end_session()
            except Exception as e:
                print(f"Error ending session: {e}")

        signal.signal(signal.SIGINT, signal_handler)

        conversation_id = conversation.wait_for_session_end()
        print(f"Conversation ID: {conversation_id}")

    except Exception as e:
        error_text = str(e)
        print(f"Error during conversation: {error_text}")
        if "needs_authorization" in error_text or "authorization" in error_text:
            print(
                "Check that ELEVENLABS_API_KEY is correctly set and that the key "
                "has permission for the selected agent ID."
            )
    finally:
        print("Session finished, cleaning up...")
        ring_idle()
        time.sleep(1)


def manual_conversation_prompt():
    """Fallback mode when the GPIO button cannot be used."""

    print(
        "RPi.GPIO is missing or cannot be used. Press Enter to start a "
        "conversation manually."
    )
    try:
        while True:
            input("\nStart new session (Enter): ")
            start_conversation_flow()
    except KeyboardInterrupt:
        print("Exiting via CTRL+C...")
    finally:
        ring_idle()


def setup_button() -> bool:
    """Configure the GPIO button and provide helpful debug info."""

    try:
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    except RuntimeError as e:
        print("Could not configure the button via GPIO.")
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            print("RPi.GPIO typically requires root. Run the script with sudo.")
        print(f"Details: {e}")
        return False

    initial_state = GPIO.input(BUTTON_PIN)
    print(
        f"Button on GPIO {BUTTON_PIN} initialized (pull-up). Starting state: "
        f"{'PRESSED' if initial_state == GPIO.LOW else 'released'}."
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
            print("Warning: RPi.GPIO usually only works for root. Run with sudo.")

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        setup_status_led()

        if not setup_button():
            manual_conversation_prompt()
            return

        print(
            "Hotword support is removed. Press the button between GPIO 17 and "
            "GND to start a conversation (CTRL+C to exit)."
        )

        while True:
            try:
                channel = GPIO.wait_for_edge(
                    BUTTON_PIN, GPIO.FALLING, bouncetime=300, timeout=10000
                )
            except RuntimeError as e:
                print(
                    "Could not listen to the button via GPIO. Switching to "
                    "manual mode."
                )
                print(f"Details: {e}")
                manual_conversation_prompt()
                return

            if channel is None:
                print("No button press detected in 10 seconds...")
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
