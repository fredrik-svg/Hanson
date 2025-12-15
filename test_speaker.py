#!/usr/bin/env python3
"""
Test script för att verifiera att ALSA-högtalare fungerar korrekt.

Detta skript spelar upp en testton via ALSA för att bekräfta att
ljudutgången fungerar som förväntat innan du kör huvudassistenten.
"""

import sys
import math
import struct

try:
    import pyaudio
except ImportError:
    print("Fel: pyaudio är inte installerat.")
    print("Installera det med: pip install pyaudio")
    print("Du kan också behöva: sudo apt-get install portaudio19-dev")
    sys.exit(1)


def test_speaker():
    """Spelar upp en 440 Hz testton (A4) i 2 sekunder.
    
    Returns:
        bool: True om testet lyckades, False om det misslyckades.
    
    Raises:
        Exception: Om PyAudio inte kan initialiseras eller spela upp ljud.
    """
    
    print("=" * 60)
    print("ALSA Högtalare Test")
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
        # Initiera PyAudio
        audio = pyaudio.PyAudio()
        
        # Lista tillgängliga utgångsenheter
        print("Tillgängliga ljudutgångar:")
        print("-" * 60)
        default_output = None
        try:
            default_output = audio.get_default_output_device_info()
            print(f"Standard utgång: {default_output['name']}")
            print(f"  Index: {default_output['index']}")
            print(f"  Kanaler: {default_output['maxOutputChannels']}")
            print(f"  Sample rate: {int(default_output['defaultSampleRate'])} Hz")
        except OSError as e:
            print(f"Ingen standardutgång hittades: {e}")
            print("\nKonfigurera ALSA eller anslut en högtalare och försök igen.")
            return False
        
        print()
        print(f"Spelar upp {FREQUENCY} Hz testton i {DURATION} sekunder...")
        print("Du bör höra en ren ton från din högtalare.")
        print()
        
        # Öppna stream
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
        print("Om du hörde tonen fungerar din högtalare korrekt via ALSA.")
        print("Om du inte hörde något, kontrollera:")
        print("  1. Att högtalaren är påslagen och ansluten")
        print("  2. Volymen på systemet och högtalaren")
        print("  3. ALSA-konfigurationen med: aplay -l")
        print("  4. Bluetooth-anslutningen om du använder Bluetooth-högtalare")
        print()
        
        return True
        
    except Exception as e:
        print(f"✗ Fel vid uppspelning: {e}")
        print()
        print("Felsökning:")
        print("  - Kontrollera att portaudio är installerat: sudo apt-get install portaudio19-dev")
        print("  - Lista ALSA-enheter: aplay -l")
        print("  - Testa ALSA direkt: speaker-test -t wav -c 2")
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
