#!/usr/bin/python

import time
import sys
from neopixel import *


# Define functions which animate LEDs in various ways.
def color_wipe(strip, r, g, b, wait_ms=0):
    """
    Wipe color across display a pixel at a time.
    """
    color = Color(r, g, b)
    for i in range(strip.numPixels()):
        # print("%s [%s %s %s]" % (i, r, g, b))
        strip.setPixelColor(i, color)
        if wait_ms > 0:
            strip.show()
        time.sleep(wait_ms/1000.0)
    strip.show()
    color = [r,g,b]

def color_array(strip, pixels):
    for pix in pixels:
        i, r, g, b = pix
        color = Color(r, g, b)
        print "color %s" % color
        strip.setPixelColor(i, color)
    strip.show()

# Create NeoPixel object with appropriate configuration.
def create_strip(led_count):
    LED_PIN     = 18      # GPIO pin connected to the pixels (must support PWM!).
    LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
    LED_DMA     = 5       # DMA channel to use for generating signal (try 5)
    LED_INVERT  = False   # True to invert the signal (when using NPN transistor level shift)

    strip = Adafruit_NeoPixel(led_count, # num
            LED_PIN,  # pin
            LED_FREQ_HZ,  # freq
            LED_DMA,  # dma
            LED_INVERT, # invert
	    255)  # brightness
    # Intialize the library (must be called once before other functions).
    strip.begin()
    color_wipe(strip, 255,   0,   0, 5)
    color_wipe(strip,   0, 255,   0, 5)
    color_wipe(strip,   0,   0, 255, 5)
    color_wipe(strip,   0,   0,   0, 5)
 
    return strip



if __name__ == '__main__':
    # create NeoPixel object with appropriate configuration.
    # Intialize the library (must be called once before other functions).
    if len(sys.argv) < 4:
        print("lamp.py red green blue delay ms (default=0)")
        exit(-1)
    r = int(sys.argv[1])
    g = int(sys.argv[2])
    b = int(sys.argv[3])
    wait = 0
    if len(sys.argv) > 4:
	wait = int(sys.argv[4])

    print ("color wipe [%s, %s, %s] %s s" % (r, g, b, wait) )
    strip = create_strip(64)
    color_wipe(strip, r,g,b, wait)
    print("done")
