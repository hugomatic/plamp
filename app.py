#!/usr/bin/python

# This script is responsible for taking JSON-encoded POSTs and converting them to ROS message publications, destined for the
# copilot, which has the execution logic.

# Python imports
import json
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

port_number = 5000

# parse cmd line args
 


if len(sys.argv) >= 2:
   try:
       port_number = int(sys.argv[1])
   except ValueError:
       print "Argument 3 '%s' is not a valid port number" % sys.argv[2]

g_server_host = "plamp.io"

def postData(route, data):
   uri = g_server_host + route
   print "about to post to %s" % uri 
   jsonStr = json.dumps(data)
   print "posting [%s]  %s" % (route, jsonStr)
   headers = {'Content-Type': 'application/json', 'Accept': 'text/plain'}
   r = requests.post (uri, headers=headers, data = jsonStr)
   if r.status_code != requests.codes.ok:
     print "ERROR posting to server %s" % r 
   else:
     print "return %s\n" % r
     return r.json()


app = Flask(__name__)

#
# http://flask-cors.readthedocs.org/en/latest/
# sudo pip pip install -U flask-cors 
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
    def get_options():
        options = {'set':'set', 'mix':'mix', 'blink':'blink'}
        s = ""
        for k,v in options.iteritems():
            s += '<option value="%s">%s</option>\n' % (k,k)
        return s

    content = """
<html>

<script>


function get_data()
{
    var data = {};
    data['red']   = Number(document.getElementById("red_id"  ).value);
    data['green'] = Number(document.getElementById("green_id").value);
    data['blue']  = Number(document.getElementById("blue_id" ).value);
    data['wait']  = Number(document.getElementById("wait_id" ).value);
    return data; 
}

function send()
{
    var data = get_data();
    console.log('data ' + data);

    var xmlhttp;
    xmlhttp=new XMLHttpRequest();
    xmlhttp.onreadystatechange=function() {
        if (xmlhttp.readyState==4 && xmlhttp.status >= 200 && xmlhttp.status < 300) {
            document.getElementById("responseDiv").innerHTML+=xmlhttp.responseText +'<br>';
        }
    }
    xmlhttp.open("POST","/color", true);
    xmlhttp.setRequestHeader("Content-Type","application/json");
    xmlhttp.send(JSON.stringify(data));

}


</script>
<body>

<h1>""" + "PLAMP" + """</h1>
RGB values (0-255), wait in ms<br>
Red <input type="text" size="25" value="128" id="red_id" /><br>
Green <input type="text" size="25" value="128" id="green_id" /><br>
Blue <input type="text" size="25" value="128" id="blue_id" /><br>
Wait <input type="text" size="25" value="20" id="wait_id" /><br>

<!--
<select name="mode" id="mode_id">
    """ + get_options() + """
</select><br>
-->


<button onclick="send()" >Send command</button>

<h3>Response</h3>
<div id="responseDiv"/>

</body>
</html>
"""
    return Response(content, mimetype="text/html") 


    

@app.route('/color', methods = ['POST'])
def set_color():
   
    print ("set_color: %s" % request.method)
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
        drone.loginfo("Wrong color message received. Abort !!!")
        abort(400)

    red = request.json['red']
    green = request.json['green']
    blue = request.json['blue']

    # delay for pixels to switch on
    wait = 25
    if 'wait' in request.json:
       wait = request.json['wait']

    lamp.color_wipe(red, green, blue, wait)
    return jsonify( { 'color': [red, green, blue] } ), 200


if __name__ == '__main__':
    print ("Running server on port %s" % port_number)
    debug = False 
    app.run(host= '0.0.0.0', port=port_number, debug=debug)

