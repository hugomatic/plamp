#!/usr/bin/python

import time
import sys
from neopixel import *

LED_COUNT = 64
LED_PIN     = 18      # GPIO pin connected to the pixels (must support PWM!).
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA     = 5       # DMA channel to use for generating signal (try 5)
LED_INVERT  = False   # True to invert the signal (when using NPN transistor level shift)


# Define functions which animate LEDs in various ways.
def color_wipe(r, g, b, wait_ms=50):
    """
    Wipe color across display a pixel at a time.
    """
    color = Color(r, g, b)
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms/1000.0)


# Create NeoPixel object with appropriate configuration.
strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT)
# Intialize the library (must be called once before other functions).
strip.begin()

if __name__ == '__main__':
    # create NeoPixel object with appropriate configuration.
    strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT)
    # Intialize the library (must be called once before other functions).
    strip.begin()
    if len(sys.argv) < 4:
        print("lamp.py red green blue")
	exit(-1)
    r = int(sys.argv[1])
    g = int(sys.argv[2])
    b = int(sys.argv[3])

    print ("color [%s, %s, %s]" % (r,g,b) )
    color_wipe(r,g,b, 50)
