#!/usr/bin/env python3
"""
Test script för att verifiera att högtalare fungerar korrekt.

Detta skript listar alla tillgängliga ljudutgångar (inklusive Bluetooth)
och spelar upp en testton för att bekräfta att ljudutgången fungerar
som förväntat innan du kör huvudassistenten.

OBS: Bluetooth-högtalare visas INTE i 'aplay -l' eftersom det bara listar
ALSA hårdvaruenheter. Bluetooth hanteras av PulseAudio/PipeWire och visas
i PyAudio-listan som detta skript genererar.
"""

import contextlib
import ctypes
import math
import struct
import sys
from typing import Iterator, Optional

try:
    import pyaudio
except ImportError:
    print("Fel: pyaudio är inte installerat.")
    print("Installera det med: pip install pyaudio")
    print("Du kan också behöva: sudo apt-get install portaudio19-dev")
    sys.exit(1)

ERROR_HANDLER_FUNC = ctypes.CFUNCTYPE(
    None, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p
)

try:
    alsa = ctypes.cdll.LoadLibrary("libasound.so.2")
except OSError:
    alsa = None


def _ignore_alsa_errors(
    filename: Optional[bytes],
    line: int,
    function: Optional[bytes],
    err: int,
    fmt: Optional[bytes],
) -> None:
    """No-op error handler to silence ALSA noise when enumerating devices."""


c_error_handler = ERROR_HANDLER_FUNC(_ignore_alsa_errors)


@contextlib.contextmanager
def suppress_alsa_errors() -> Iterator[None]:
    """Temporarily silence ALSA stderr chatter under device probing."""

    if alsa is None:
        # ALSA-biblioteket saknas, så det finns inget att tysta
        yield
        return

    try:
        alsa.snd_lib_error_set_handler(c_error_handler)
        yield
    finally:
        alsa.snd_lib_error_set_handler(None)


def detect_device_type(device_name: str) -> str:
    """Detect device type from its name.
    
    Args:
        device_name: The name of the audio device.
    
    Returns:
        A formatted string label like ' [BLUETOOTH]', ' [HDMI]', ' [USB]',
        or empty string if device type is unknown.
    """
    name_lower = device_name.lower()
    if 'bluetooth' in name_lower or 'bluez' in name_lower:
        return " [BLUETOOTH]"
    elif 'hdmi' in name_lower:
        return " [HDMI]"
    elif 'usb' in name_lower:
        return " [USB]"
    return ""


def test_speaker():
    """Spelar upp en 440 Hz testton (A4) i 2 sekunder.
    
    Returns:
        bool: True om testet lyckades, False om det misslyckades.
    
    Raises:
        Exception: Om PyAudio inte kan initialiseras eller spela upp ljud.
    """
    
    print("=" * 60)
    print("ALSA/PipeWire Högtalare Test")
    print("=" * 60)
    print()
    
    # Audio parametrar
    SAMPLE_RATE = 44100
    FREQUENCY = 440  # A4 ton
    DURATION = 2  # sekunder
    VOLUME = 0.3  # 0.0 till 1.0
    
    audio = None
    stream = None
    
    try:
        # Initiera PyAudio utan att spamma ALSA-varningar
        with suppress_alsa_errors():
            audio = pyaudio.PyAudio()
        
        # Lista ALLA tillgängliga utgångsenheter
        print("Tillgängliga ljudutgångar:")
        print("-" * 60)
        device_count = audio.get_device_count()
        output_devices = []
        
        for i in range(device_count):
            try:
                with suppress_alsa_errors():
                    device_info = audio.get_device_info_by_index(i)
                if device_info['maxOutputChannels'] > 0:
                    output_devices.append(device_info)
                    device_type = detect_device_type(device_info['name'])
                    
                    print(f"  [{i}] {device_info['name']}{device_type}")
                    print(f"      Kanaler: {device_info['maxOutputChannels']}, "
                          f"Sample rate: {int(device_info['defaultSampleRate'])} Hz")
            except (OSError, IOError):
                # Skip devices that can't be queried (expected for some virtual devices)
                pass
        
        if not output_devices:
            print("Inga utgångsenheter hittades!")
            print("\nKonfigurera PulseAudio/PipeWire eller anslut en högtalare och försök igen.")
            return False
        
        print()
        print("-" * 60)
        
        # Hämta standardenhet
        default_output = None
        try:
            with suppress_alsa_errors():
                default_output = audio.get_default_output_device_info()
            device_type = detect_device_type(default_output['name'])
            
            print(f"Standard utgång: {default_output['name']}{device_type}")
            print(f"  Index: {default_output['index']}")
            print(f"  Kanaler: {default_output['maxOutputChannels']}")
            print(f"  Sample rate: {int(default_output['defaultSampleRate'])} Hz")
        except OSError as e:
            print(f"Ingen standardutgång hittades: {e}")
            print("\nKonfigurera PulseAudio/PipeWire eller anslut en högtalare och försök igen.")
            return False
        
        print()
        print(f"Spelar upp {FREQUENCY} Hz testton i {DURATION} sekunder...")
        print("Du bör höra en ren ton från din högtalare.")
        print()
        
        # Öppna stream
        with suppress_alsa_errors():
            stream = audio.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=SAMPLE_RATE,
                output=True,
                output_device_index=default_output['index']
            )
        
        # Generera och spela upp sinus-våg
        samples_per_buffer = 1024
        num_buffers = math.ceil((SAMPLE_RATE * DURATION) / samples_per_buffer)
        
        for i in range(num_buffers):
            # Generera samples för denna buffer
            samples = []
            for j in range(samples_per_buffer):
                sample_number = i * samples_per_buffer + j
                t = sample_number / SAMPLE_RATE
                sample = VOLUME * math.sin(2 * math.pi * FREQUENCY * t)
                samples.append(sample)
            
            # Konvertera till bytes och skriv till stream
            data = struct.pack('f' * len(samples), *samples)
            stream.write(data)
        
        print("✓ Testton spelad upp!")
        print()
        print("Om du hörde tonen fungerar din högtalare korrekt!")
        print()
        print("Om du inte hörde något, kontrollera:")
        print("  1. Att högtalaren är påslagen och ansluten")
        print("  2. Volymen på systemet och högtalaren")
        print("  3. För Bluetooth-högtalare:")
        print("     - Para enheten med: bluetoothctl")
        print("     - Kontrollera anslutning: bluetoothctl info <MAC-adress>")
        print("     - Sätt som standard (Debian Trixie): wpctl set-default <node-id>")
        print("  4. För andra enheter, kontrollera ALSA: aplay -l")
        print()
        print("OBS: Bluetooth-högtalare visas INTE i 'aplay -l' (endast hårdvaruenheter).")
        print("     De hanteras av PulseAudio/PipeWire och visas i listan ovan.")
        print()
        
        return True
        
    except Exception as e:
        print(f"✗ Fel vid uppspelning: {e}")
        print()
        print("Felsökning:")
        print("  - Kontrollera att portaudio är installerat: sudo apt-get install portaudio19-dev")
        print("  - För Debian Trixie: sudo apt-get install pipewire-alsa")
        print("  - Lista hårdvaruenheter (HDMI, USB, etc): aplay -l")
        print("  - Testa ALSA direkt: speaker-test -t wav -c 2")
        print("  - För Bluetooth, använd: bluetoothctl och wpctl/pactl")
        print()
        print("OBS: Bluetooth-högtalare visas INTE i 'aplay -l' - de hanteras av")
        print("     PulseAudio/PipeWire. Använd detta skript för att se alla enheter.")
        return False
        
    finally:
        # Stäng stream och PyAudio
        if stream:
            stream.stop_stream()
            stream.close()
        if audio:
            audio.terminate()


def main():
    """Huvudfunktion som kör högtalartest och hanterar avslutningskoder."""
    try:
        success = test_speaker()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest avbrutet av användaren.")
        sys.exit(130)


if __name__ == "__main__":
    main()

