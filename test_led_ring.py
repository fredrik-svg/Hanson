#!/usr/bin/env python3
"""
Test script for WS2812b LED Ring functionality.
This script validates the LED ring configuration and functions.

Usage:
    export LED_RING_ENABLED=1
    export LED_RING_PIN=18
    export LED_RING_COUNT=12
    export LED_RING_BRIGHTNESS=128
    sudo -E python3 test_led_ring.py
"""

import os
import sys
import time

# Set environment variables for testing if not already set
if not os.getenv("LED_RING_ENABLED"):
    os.environ["LED_RING_ENABLED"] = "1"
if not os.getenv("LED_RING_PIN"):
    os.environ["LED_RING_PIN"] = "18"
if not os.getenv("LED_RING_COUNT"):
    os.environ["LED_RING_COUNT"] = "12"
if not os.getenv("LED_RING_BRIGHTNESS"):
    os.environ["LED_RING_BRIGHTNESS"] = "128"

print("=" * 60)
print("WS2812b LED Ring Test")
print("=" * 60)
print(f"LED_RING_ENABLED: {os.getenv('LED_RING_ENABLED')}")
print(f"LED_RING_PIN: {os.getenv('LED_RING_PIN')}")
print(f"LED_RING_COUNT: {os.getenv('LED_RING_COUNT')}")
print(f"LED_RING_BRIGHTNESS: {os.getenv('LED_RING_BRIGHTNESS')}")
print("=" * 60)

# Check if rpi_ws281x is available
try:
    from rpi_ws281x import PixelStrip, Color
    print("\n✓ rpi_ws281x library is available")
except ImportError as e:
    print("\n✗ rpi_ws281x library is NOT available")
    print(f"  Error: {e}")
    print("\n  Install it with: pip install rpi-ws281x")
    sys.exit(1)

# Test LED ring configuration values
try:
    LED_RING_COUNT = int(os.getenv("LED_RING_COUNT", "12"))
    LED_RING_PIN = int(os.getenv("LED_RING_PIN", "18"))
    LED_RING_BRIGHTNESS = int(os.getenv("LED_RING_BRIGHTNESS", "128"))
    
    print(f"\n✓ Configuration values are valid:")
    print(f"  - LEDs: {LED_RING_COUNT}")
    print(f"  - GPIO Pin: {LED_RING_PIN}")
    print(f"  - Brightness: {LED_RING_BRIGHTNESS}/255")
except ValueError as e:
    print(f"\n✗ Invalid configuration value: {e}")
    sys.exit(1)

# Try to initialize the LED ring
print("\nAttempting to initialize LED ring...")
try:
    LED_FREQ_HZ = 800000
    LED_DMA = 10
    LED_INVERT = False
    LED_CHANNEL = 0
    
    strip = PixelStrip(
        LED_RING_COUNT,
        LED_RING_PIN,
        LED_FREQ_HZ,
        LED_DMA,
        LED_INVERT,
        LED_RING_BRIGHTNESS,
        LED_CHANNEL
    )
    
    strip.begin()
    print("✓ LED ring initialized successfully!")
    
    # Test different colors
    print("\nTesting LED colors (2 seconds each)...")
    
    print("  - All LEDs OFF (idle)")
    for i in range(LED_RING_COUNT):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()
    time.sleep(2)
    
    print("  - Blue (listening)")
    for i in range(LED_RING_COUNT):
        strip.setPixelColor(i, Color(0, 0, 255))
    strip.show()
    time.sleep(2)
    
    print("  - Yellow (thinking)")
    for i in range(LED_RING_COUNT):
        strip.setPixelColor(i, Color(255, 255, 0))
    strip.show()
    time.sleep(2)
    
    print("  - Green (speaking)")
    for i in range(LED_RING_COUNT):
        strip.setPixelColor(i, Color(0, 255, 0))
    strip.show()
    time.sleep(2)
    
    print("  - All LEDs OFF (cleanup)")
    for i in range(LED_RING_COUNT):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()
    
    print("\n✓ All tests passed!")
    print("\nThe LED ring is working correctly.")
    
except Exception as e:
    print(f"\n✗ Failed to initialize or control LED ring")
    print(f"  Error: {e}")
    print("\n  Common issues:")
    print("  - Make sure you're running with sudo (required for PWM)")
    print("  - Verify GPIO 18 is not being used by another process")
    print("  - Check that the LED ring is properly connected")
    print("  - Ensure your Raspberry Pi supports hardware PWM on GPIO 18")
    sys.exit(1)
