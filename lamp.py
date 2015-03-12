#!/usr/bin/python

import time
import sys
from neopixel import *


# Define functions which animate LEDs in various ways.
def color_wipe(strip, r, g, b, wait_ms):
    """
    Wipe color across display a pixel at a time.
    """
    color = Color(r, g, b)
    for i in range(strip.numPixels()):
	print("%s [%s %s %s]" % (i, r, g, b))
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms/1000.0)


# Create NeoPixel object with appropriate configuration.
def create_strip():
    LED_COUNT   = 64
    LED_PIN     = 18      # GPIO pin connected to the pixels (must support PWM!).
    LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
    LED_DMA     = 5       # DMA channel to use for generating signal (try 5)
    LED_INVERT  = False   # True to invert the signal (when using NPN transistor level shift)

    strip = Adafruit_NeoPixel(LED_COUNT,
            LED_PIN,
            LED_FREQ_HZ,
            LED_DMA,
            LED_INVERT)
    # Intialize the library (must be called once before other functions).
    strip.begin()
    return strip



if __name__ == '__main__':
    # create NeoPixel object with appropriate configuration.
    # Intialize the library (must be called once before other functions).
    if len(sys.argv) < 4:
        print("lamp.py red green blue (ms)")
        exit(-1)
    r = int(sys.argv[1])
    g = int(sys.argv[2])
    b = int(sys.argv[3])
    wait = 0
    if len(sys.argv) > 4:
	wait = int(sys.argv[4])

    print ("color wipe [%s, %s, %s] %s s" % (r, g, b, wait) )
    strip = create_strip()
    color_wipe(strip, r,g,b, wait)
    print("done")
