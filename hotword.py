
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

from pixel_ring import pixel_ring

BUTTON_PIN = 17

GPIO_AVAILABLE = importlib.util.find_spec("RPi.GPIO") is not None

if GPIO_AVAILABLE:
    import RPi.GPIO as GPIO

load_dotenv()

agent_id = os.getenv("ELEVENLABS_AGENT_ID")
api_key = os.getenv("ELEVENLABS_API_KEY")

if not agent_id:
    raise RuntimeError("ELEVENLABS_AGENT_ID is not set in the environment")
if not api_key:
    raise RuntimeError("ELEVENLABS_API_KEY is not set in the environment")

elevenlabs = ElevenLabs(api_key=api_key)

# Dynamiska variabler som kan användas i din agentprompt
dynamic_vars = {
    "user_name": "Fredrik",
    "greeting": "Hej",
    "language": "svenska",
}

config = ConversationInitiationData(dynamic_variables=dynamic_vars)

def ring_idle():
    """LED-ring av (idle-läge)."""
    try:
        pixel_ring.off()
    except Exception as e:
        print(f"Kunde inte stänga av LED-ring: {e}")


def ring_listening():
    """LED indikerar att assistenten är väckt och redo att lyssna."""
    try:
        pixel_ring.wakeup()
    except Exception as e:
        print(f"Kunde inte sätta LED till wakeup: {e}")


def ring_thinking():
    """LED indikerar att agenten tänker/bearbetar."""
    try:
        pixel_ring.think()
    except Exception as e:
        print(f"Kunde inte sätta LED till think: {e}")


def ring_speaking():
    """LED indikerar att agenten pratar."""
    try:
        pixel_ring.speak()
    except Exception as e:
        print(f"Kunde inte sätta LED till speak: {e}")


def create_conversation():
    """Skapa en ny ElevenLabs-konversation."""

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
    """Starta en ElevenLabs-session och hantera städning."""

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
    """Fallback-läge när GPIO-knappen inte kan användas."""

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


def main():
    ring_idle()

    if not GPIO_AVAILABLE:
        manual_conversation_prompt()
        return

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        print(
            "Hotword-stöd är borttaget. Tryck på knappen mellan GPIO 17 och "
            "GND för att starta en konversation (CTRL+C för att avsluta)."
        )

        while True:
            try:
                GPIO.wait_for_edge(BUTTON_PIN, GPIO.FALLING, bouncetime=300)
            except RuntimeError as e:
                print(
                    "Kunde inte lyssna på knappen via GPIO. Växlar till "
                    "manuellt läge."
                )
                print(f"Detaljer: {e}")
                manual_conversation_prompt()
                return

            start_conversation_flow()
    except KeyboardInterrupt:
        print("Avslutar via CTRL+C...")
    finally:
        ring_idle()
        if GPIO_AVAILABLE:
            GPIO.cleanup()


if __name__ == "__main__":
    main()
