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

# parse cmd line args
 


if len(sys.argv) >= 2:
   try:
       port_number = int(sys.argv[1])
   except ValueError:
       print "Argument 3 '%s' is not a valid port number" % sys.argv[2]

g_server_host = "plamp.io"


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
cors = CORS(app)


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


strip = lamp.create_strip()    

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
        print "request.json is None"
    bad = False
    if not 'red' in request.json:
        print("no red")
        bad = True
    if not 'green' in request.json:
        print("no green")
        bad = True
    if not 'blue' in request.json:
        print("no blue")
        bad = True

    if not request.json or bad:
        print("Wrong color message received. Abort !!!")
        abort(400)

    red = request.json['red']
    green = request.json['green']
    blue = request.json['blue']

    # delay for pixels to switch on
    wait = 25
    if 'wait' in request.json:
       wait = request.json['wait']

    lamp.color_wipe(strip, red, green, blue, wait)
    return jsonify( { 'color': [red, green, blue] } ), 200


if __name__ == '__main__':
    print ("Running server on port %s" % port_number)
    debug = True 
    app.run(host= '0.0.0.0', port=port_number, debug=debug)

