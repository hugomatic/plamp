#!/usr/bin/python

# This script is responsible for taking JSON-encoded POSTs and converting them to ROS message publications, destined for the
# copilot, which has the execution logic.

# Python imports
import json
import os
import sys

# the neopixel stuff
import lamp

# sudo apt-get install pip
# flask imports 

# sudo pip install Flask
# sudo pip install -U flask-cors
from flask import Flask
from flask import jsonify
from flask import request
from flask import Response
from flask.ext.cors import CORS

# sudo pip install requests
import requests

port_number = 80
debug = False
LED_COUNT = 128


# parse cmd line args
if len(sys.argv) >= 2:
   try:
       port_number = int(sys.argv[1])
   except ValueError:
       print "Argument 3 '%s' is not a valid port number" % sys.argv[2]

if len(sys.argv) >= 3:
   try:
       if sys.argv[2] == 'debug':
           debug = True
   except ValueError:
       print "Argument 3 '%s' is not a valid port number" % sys.argv[2]



app = Flask(__name__)

#
# http://flask-cors.readthedocs.org/en/latest/
# sudo pip install -U flask-cors 
#
# CORS allows this server to  accept requests
# from a different domain (for all routes in this case)
# by changing the following HTTP headers:
#
# 'Access-Control-Allow-Origin'
# 'Access-Control-Allow-Methods'
# 'Access-Control-Max-Age'
# 'Access-Control-Allow-Headers' 

cors = CORS(app, resources="/*", allow_headers="Content-Type")


@app.route('/config', methods = ['GET'])
def get_config():
    print "CONFIG!"
    content = "<h1>Configure</h1>";
    return Response(content, mimetype="text/html") 


@app.route('/', methods = ['GET'])
def index():
    f = os.path.join(os.path.dirname(__file__), "plamp.html")
    print "serving %s" % f
    content = open(f).read()
    return Response(content, mimetype="text/html") 


strip = lamp.create_strip(LED_COUNT)    

@app.route('/color_array', methods = ['POST'])
def post_colors():
    if not request.json:
        print "request.json is None, Abort"
        abort(400)

    print("request %s" % request.json)

    pixels = request.json  
    lamp.color_array(strip, pixels)        
    return jsonify( { 'count': len(pixels) } ), 200

@app.route('/color_wipe', methods = ['POST'])
def post_color_wipe():
    if not request.json:
        print "request.json is None, Abort"
        abort(400)

    red = request.json[0]
    green = request.json[1]
    blue = request.json[2]
    wait = request.json[3]

    lamp.color_wipe(strip, red, green, blue, wait)
    return jsonify( { 'color': [red, green, blue] } ), 200


if __name__ == '__main__':
    print ("Running server on port %s" % port_number)
    app.run(host= '0.0.0.0', port=port_number, debug=debug)

