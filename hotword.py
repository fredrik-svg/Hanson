
import os
import signal
import sys
import time

if sys.version_info >= (3, 12):
    raise RuntimeError(
        "EfficientWord-Net currently supports Python versions below 3.12. "
        "Use Python 3.11 or lower to enable hotword detection."
    )

from eff_word_net.streams import SimpleMicStream
from eff_word_net.engine import HotwordDetector
from eff_word_net.audio_processing import Resnet50_Arc_loss

from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import (
    Conversation,
    ConversationInitiationData,
)
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

from pixel_ring import pixel_ring

convai_active = False
mic_stream = None

elevenlabs = ElevenLabs()
agent_id = os.getenv("ELEVENLABS_AGENT_ID")
api_key = os.getenv("ELEVENLABS_API_KEY")

if not agent_id:
    raise RuntimeError("ELEVENLABS_AGENT_ID is not set in the environment")
if not api_key:
    raise RuntimeError("ELEVENLABS_API_KEY is not set in the environment")

# Dynamiska variabler som kan användas i din agentprompt
dynamic_vars = {
    "user_name": "Fredrik",
    "greeting": "Hej",
    "language": "svenska",
}

config = ConversationInitiationData(
    dynamic_variables=dynamic_vars
)

base_model = Resnet50_Arc_loss()

eleven_hw = HotwordDetector(
    hotword="hey_eleven",
    model=base_model,
    reference_file=os.path.join("hotword_refs", "hey_eleven_ref.json"),
    threshold=0.7,
    relaxation_time=2,
)


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


def start_mic_stream():
    """Starta eller starta om mikrofonströmmen."""
    global mic_stream
    try:
        mic_stream = SimpleMicStream(
            window_length_secs=1.5,
            sliding_window_secs=0.75,
        )
        mic_stream.start_stream()
        print("Mikrofonström startad")
    except Exception as e:
        print(f"Fel vid start av mikrofonström: {e}")
        mic_stream = None
        time.sleep(1)


def stop_mic_stream():
    """Stäng mikrofonströmmen säkert."""
    global mic_stream
    try:
        if mic_stream:
            mic_stream = None
            print("Mikrofonström stoppad")
    except Exception as e:
        print(f"Fel vid stopp av mikrofonström: {e}")


def main():
    global convai_active

    start_mic_stream()
    ring_idle()
    print("Säg 'Hey Eleven' för att väcka assistenten")

    while True:
        if not convai_active:
            try:
                if mic_stream is None:
                    start_mic_stream()
                    continue

                frame = mic_stream.getFrame()
                result = eleven_hw.scoreFrame(frame)
                if result is None:
                    continue

                if result.get("match"):
                    print("Hotword uppfattat", result.get("confidence"))
                    stop_mic_stream()

                    print("Startar ElevenLabs-session...")
                    convai_active = True
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
                        print(f"Fel under konversation: {e}")
                    finally:
                        convai_active = False
                        print("Session slut, städar upp...")
                        ring_idle()
                        time.sleep(1)
                        start_mic_stream()
                        print("Redo för nästa hotword...")

            except KeyboardInterrupt:
                print("Avslutar via CTRL+C...")
                break
            except Exception as e:
                print(f"Fel i hotword-loop: {e}")
                mic_stream = None
                time.sleep(1)
                start_mic_stream()

    # Stäng av LED-ring vid avslut
    ring_idle()


if __name__ == "__main__":
    main()
