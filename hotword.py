
import getpass
import grp
import importlib.util
import os
import signal
import sys
import threading
import time

from dotenv import load_dotenv
import pyaudio

# Suppress ALSA warnings/errors before importing audio libraries
os.environ['ALSA_CARD'] = 'default'
os.environ['ALSA_PCM_CARD'] = 'default'

# Temporarily redirect stderr to suppress ALSA errors during import
stderr_fd = sys.stderr.fileno()
old_stderr = os.dup(stderr_fd)
devnull_fd = os.open(os.devnull, os.O_WRONLY)
os.dup2(devnull_fd, stderr_fd)

try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs.conversational_ai.conversation import (
        Conversation,
        ConversationInitiationData,
    )
    from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
finally:
    # Restore stderr
    os.dup2(old_stderr, stderr_fd)
    os.close(devnull_fd)
    os.close(old_stderr)


load_dotenv()

BUTTON_PIN = 17

GPIO_AVAILABLE = False
GPIO_IMPORT_ERROR = None
GPIO_BACKEND = None  # 'RPi.GPIO' or 'gpiod'
GPIO = None
gpiod_chip = None
gpiod_button_line = None
gpiod_led_line = None

# Try to import gpiod first (for Raspberry Pi 5 / Debian Trixie)
try:
    if importlib.util.find_spec("gpiod") is not None:
        try:
            import gpiod
            GPIO_AVAILABLE = True
            GPIO_BACKEND = 'gpiod'
        except (RuntimeError, ImportError) as e:
            GPIO_IMPORT_ERROR = e
except (ModuleNotFoundError, ImportError):
    pass

# Fall back to RPi.GPIO if gpiod is not available
if not GPIO_AVAILABLE:
    try:
        if importlib.util.find_spec("RPi.GPIO") is not None:
            try:
                import RPi.GPIO as GPIO
                GPIO_AVAILABLE = True
                GPIO_BACKEND = 'RPi.GPIO'
            except (RuntimeError, ImportError) as e:
                GPIO_IMPORT_ERROR = e
    except (ModuleNotFoundError, ImportError):
        # RPi.GPIO module not found
        pass

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
THINKING_TIMER = None


def suppress_alsa_errors(func):
    """Decorator to suppress ALSA errors during function execution."""
    def wrapper(*args, **kwargs):
        stderr_fd = sys.stderr.fileno()
        old_stderr = os.dup(stderr_fd)
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull_fd, stderr_fd)
        
        try:
            return func(*args, **kwargs)
        finally:
            os.dup2(old_stderr, stderr_fd)
            os.close(devnull_fd)
            os.close(old_stderr)
    
    return wrapper


def _complete_thinking():
    """Reset thinking blink state."""

    global THINKING_TIMER
    set_status_led(False)
    THINKING_TIMER = None


def _cancel_thinking_timer():
    """Cancel any pending thinking blink."""

    global THINKING_TIMER
    if THINKING_TIMER:
        THINKING_TIMER.cancel()
        THINKING_TIMER = None


def setup_status_led():
    """Initialize status LED via GPIO if a pin is provided."""

    global STATUS_LED_INITIALIZED, gpiod_chip, gpiod_led_line

    if not GPIO_AVAILABLE or STATUS_LED_PIN is None:
        return

    try:
        if GPIO_BACKEND == 'gpiod':
            import gpiod
            # Try to find the correct gpiochip (usually gpiochip4 on Pi 5)
            for chip_num in [4, 0, 1, 2, 3]:
                chip_path = f'/dev/gpiochip{chip_num}'
                if os.path.exists(chip_path):
                    try:
                        gpiod_chip = gpiod.Chip(chip_path)
                        gpiod_led_line = gpiod_chip.get_line(STATUS_LED_PIN)
                        initial_value = 0 if STATUS_LED_ACTIVE_HIGH else 1
                        gpiod_led_line.request(
                            consumer='hanson-led',
                            type=gpiod.LINE_REQ_DIR_OUT,
                            default_vals=[initial_value]
                        )
                        STATUS_LED_INITIALIZED = True
                        print(
                            f"Status LED controlled via {chip_path} GPIO {STATUS_LED_PIN} "
                            f"(active with {'HIGH' if STATUS_LED_ACTIVE_HIGH else 'LOW'})."
                        )
                        break
                    except (OSError, FileNotFoundError):
                        continue
            if not STATUS_LED_INITIALIZED:
                raise RuntimeError("Could not find accessible gpiochip device")
        else:  # RPi.GPIO
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
            f"Could not initialize status LED on GPIO {STATUS_LED_PIN}."
        )
        print(f"Details: {e}")
        print("Continuing without status LED. Button functionality may still work.")


def set_status_led(active: bool):
    """Turn status LED on/off if initialized."""

    if not STATUS_LED_INITIALIZED:
        return

    try:
        if GPIO_BACKEND == 'gpiod':
            value = 1 if (active == STATUS_LED_ACTIVE_HIGH) else 0
            gpiod_led_line.set_value(value)
        else:  # RPi.GPIO
            level = GPIO.HIGH if (active == STATUS_LED_ACTIVE_HIGH) else GPIO.LOW
            GPIO.output(STATUS_LED_PIN, level)
    except RuntimeError as e:
        print(f"Could not control status LED: {e}")


def ring_idle():
    """LED off (idle state)."""
    _cancel_thinking_timer()
    set_status_led(False)


def ring_listening():
    """LED indicates the assistant is awake and ready to listen."""
    _cancel_thinking_timer()
    set_status_led(True)


def ring_thinking():
    """LED indicates the agent is thinking/processing."""
    global THINKING_TIMER

    if THINKING_TIMER:
        THINKING_TIMER.cancel()
        THINKING_TIMER = None

    set_status_led(True)

    if THINKING_BLINK_SECONDS > 0:
        THINKING_TIMER = threading.Timer(
            THINKING_BLINK_SECONDS, _complete_thinking
        )
        THINKING_TIMER.start()


def ring_speaking():
    """LED indicates the agent is speaking."""
    _cancel_thinking_timer()
    set_status_led(True)


def validate_audio_environment() -> bool:
    """Check for a usable default input/output audio device.

    Returns False (with a helpful message) if no audio backend is available or the
    default device rejects the required sample format. This prevents the ElevenLabs
    session threads from crashing on startup in environments without ALSA.
    """

    audio = None
    try:
        audio = pyaudio.PyAudio()
        try:
            input_device = audio.get_default_input_device_info()
            output_device = audio.get_default_output_device_info()
        except OSError as e:
            print("No default audio device is available. Configure ALSA or set the "
                  "PULSE_SERVER to a reachable instance before starting a session.")
            print(f"Details: {e}")
            return False

        # Validate that the default devices can accept the typical stream format
        # used by the ElevenLabs client.
        try:
            audio.is_format_supported(
                rate=44100,
                input_device=input_device.get("index"),
                input_channels=1,
                input_format=pyaudio.paInt16,
                output_device=output_device.get("index"),
                output_channels=1,
                output_format=pyaudio.paInt16,
            )
        except ValueError as e:
            print("The default audio device does not support 16-bit mono 44.1kHz "
                  "streams required by the assistant.")
            print(f"Details: {e}")
            return False

        return True
    finally:
        if audio:
            audio.terminate()


@suppress_alsa_errors
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
        if not validate_audio_environment():
            print("Audio setup is incomplete; skipping session start.")
            return

        conversation = create_conversation()
        
        # Suppress ALSA errors during audio stream initialization
        stderr_fd = sys.stderr.fileno()
        old_stderr = os.dup(stderr_fd)
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull_fd, stderr_fd)
        
        try:
            conversation.start_session()
        finally:
            os.dup2(old_stderr, stderr_fd)
            os.close(devnull_fd)
            os.close(old_stderr)

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

    print("\n" + "="*60)
    print("GPIO button is not available - using manual mode")
    print("="*60)
    print("\nPress Enter to start a conversation manually.")
    print("See GPIO_PERMISSIONS.md for instructions on enabling GPIO button support.")
    print("="*60 + "\n")
    
    try:
        while True:
            input("Start new session (Enter): ")
            start_conversation_flow()
    except KeyboardInterrupt:
        print("Exiting via CTRL+C...")
    finally:
        ring_idle()


def is_user_in_gpio_group() -> bool:
    """Check if the current user is a member of the gpio group."""
    try:
        user_groups = [grp.getgrgid(g).gr_name for g in os.getgroups()]
        return 'gpio' in user_groups
    except (KeyError, OSError):
        return False


def setup_button() -> bool:
    """Configure the GPIO button and provide helpful debug info."""

    global gpiod_chip, gpiod_button_line

    try:
        if GPIO_BACKEND == 'gpiod':
            import gpiod
            # Try to find the correct gpiochip (usually gpiochip4 on Pi 5)
            for chip_num in [4, 0, 1, 2, 3]:
                chip_path = f'/dev/gpiochip{chip_num}'
                if os.path.exists(chip_path):
                    try:
                        if gpiod_chip is None:
                            gpiod_chip = gpiod.Chip(chip_path)
                        gpiod_button_line = gpiod_chip.get_line(BUTTON_PIN)
                        gpiod_button_line.request(
                            consumer='hanson-button',
                            type=gpiod.LINE_REQ_EV_FALLING_EDGE,
                            flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP
                        )
                        initial_state = gpiod_button_line.get_value()
                        print(
                            f"Button on {chip_path} GPIO {BUTTON_PIN} initialized (pull-up). "
                            f"Starting state: {'PRESSED' if initial_state == 0 else 'released'}."
                        )
                        return True
                    except (OSError, FileNotFoundError):
                        continue
            raise RuntimeError("Could not find accessible gpiochip device")
        else:  # RPi.GPIO
            GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            initial_state = GPIO.input(BUTTON_PIN)
            print(
                f"Button on GPIO {BUTTON_PIN} initialized (pull-up). Starting state: "
                f"{'PRESSED' if initial_state == GPIO.LOW else 'released'}."
            )
            return True
    except RuntimeError as e:
        print("Could not configure the button via GPIO.")
        print(f"Details: {e}")
        
        # Provide helpful troubleshooting based on the situation
        is_root = hasattr(os, "geteuid") and os.geteuid() == 0
        in_gpio_group = is_user_in_gpio_group()
        
        if not is_root and not in_gpio_group:
            username = getpass.getuser()
            print("\nTroubleshooting:")
            print(f"1. Add your user to the gpio group: sudo usermod -a -G gpio {username}")
            if GPIO_BACKEND == 'gpiod':
                print("2. Verify permissions: ls -la /dev/gpiochip*")
                print("3. Install the udev rules: sudo cp 99-gpio.rules /etc/udev/rules.d/")
            else:
                print("2. Install the udev rules: sudo cp 99-gpio.rules /etc/udev/rules.d/")
            print("4. Reload udev rules: sudo udevadm control --reload-rules && sudo udevadm trigger")
            print("5. Log out and log back in (or reboot)")
            print(f"\nAlternatively, run with sudo: sudo {sys.executable} hotword.py")
        elif not is_root and in_gpio_group:
            print("\nYou are in the gpio group, but GPIO access still failed.")
            print("Try these troubleshooting steps:")
            print("1. Verify udev rules are installed: ls -la /etc/udev/rules.d/99-gpio.rules")
            if GPIO_BACKEND == 'gpiod':
                print("2. Check /dev/gpiochip* permissions: ls -la /dev/gpiochip*")
            else:
                print("2. Check /dev/gpiomem permissions: ls -la /dev/gpiomem")
            print("3. Reload udev rules: sudo udevadm control --reload-rules && sudo udevadm trigger")
            print("4. Log out and log back in, or reboot to ensure group membership is active")
            print("\nFor detailed help, see GPIO_PERMISSIONS.md")
        else:
            print("Unexpected GPIO error. See GPIO_PERMISSIONS.md for troubleshooting.")
        
        return False


def main():
    ring_idle()

    if not GPIO_AVAILABLE:
        if GPIO_IMPORT_ERROR:
            print("\nGPIO module was found but could not be imported.")
            print(f"Error details: {GPIO_IMPORT_ERROR}")
            print("\nThis may indicate a permissions or installation issue.")
            print("See GPIO_PERMISSIONS.md for troubleshooting steps.")
        else:
            print("\nNo GPIO module is installed.")
            print("This is expected on non-Raspberry Pi systems.")
        manual_conversation_prompt()
        return

    try:
        print(f"Using GPIO backend: {GPIO_BACKEND}")
        print("Using GPIO LED if configured; otherwise running without light.")

        is_root = hasattr(os, "geteuid") and os.geteuid() == 0
        in_gpio_group = is_user_in_gpio_group()
        
        if not is_root and not in_gpio_group:
            print("\nWarning: You are not in the gpio group.")
            print("GPIO access may fail. See GPIO_PERMISSIONS.md for setup instructions.")
        elif not is_root and in_gpio_group:
            print("Running as non-root user in gpio group (recommended setup).")

        if GPIO_BACKEND == 'RPi.GPIO':
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

        button_event = threading.Event()

        if GPIO_BACKEND == 'gpiod':
            # For gpiod, we need to poll for events
            def poll_button():
                import gpiod
                last_debounce_time = 0
                debounce_delay = 0.3  # 300ms debounce
                
                while True:
                    try:
                        if gpiod_button_line.event_wait(nsec=100000000):  # 100ms timeout
                            event = gpiod_button_line.event_read()
                            current_time = time.time()
                            if current_time - last_debounce_time > debounce_delay:
                                button_event.set()
                                last_debounce_time = current_time
                    except Exception as e:
                        print(f"Error reading button event: {e}")
                        break

            button_thread = threading.Thread(target=poll_button, daemon=True)
            button_thread.start()
        else:  # RPi.GPIO
            def button_callback(channel):
                """Callback for button press detection."""
                button_event.set()

            try:
                GPIO.add_event_detect(
                    BUTTON_PIN, GPIO.FALLING, callback=button_callback, bouncetime=300
                )
            except RuntimeError as e:
                print(
                    "Could not set up button event detection via GPIO. "
                    "Switching to manual mode."
                )
                print(f"Details: {e}")
                manual_conversation_prompt()
                return

        while True:
            if button_event.wait(timeout=0.1):
                button_event.clear()
                start_conversation_flow()
    except KeyboardInterrupt:
        print("Avslutar via CTRL+C...")
    finally:
        ring_idle()
        if GPIO_AVAILABLE:
            if GPIO_BACKEND == 'gpiod':
                # Release gpiod lines
                if gpiod_button_line:
                    try:
                        gpiod_button_line.release()
                    except Exception as e:
                        print(f"Warning: Could not release button line: {e}")
                if gpiod_led_line:
                    try:
                        gpiod_led_line.release()
                    except Exception as e:
                        print(f"Warning: Could not release LED line: {e}")
                if gpiod_chip:
                    try:
                        gpiod_chip.close()
                    except Exception as e:
                        print(f"Warning: Could not close GPIO chip: {e}")
            else:  # RPi.GPIO
                try:
                    GPIO.remove_event_detect(BUTTON_PIN)
                except (RuntimeError, ValueError) as e:
                    print(f"Warning: Could not remove event detection: {e}")
                GPIO.cleanup()


if __name__ == "__main__":
    main()
