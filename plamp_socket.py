#!/usr/bin/env python

import os
import time

from socketio import socketio_manage
from socketio.server import SocketIOServer
from socketio.namespace import BaseNamespace
import lamp

min_wait_time = 0.075
port = 80
led_count = 1 * 64

R=0
G=0
B=0

strip = lamp.create_strip(led_count)

timestamp = time.time() 

def color_wipe(str):
    global R
    global G
    global B
    global timestamp
    print "%s color_wipe %s" % (timestamp, str)
    data = eval(str)
    r = int(data[0])
    g = int(data[1])
    b = int(data[2])
    w = int(data[3])
    age = time.time() - timestamp
    if age > min_wait_time:
        lamp.color_wipe(strip, r, g, b, w)
        R = r
        G = g
        B = b
        timestamp = time.time()
        return  data
    return None
        
def color_array(str):
    print "on color array"
    print "data %s" % str
    pixels = eval(str)
    print "PIXELS %s" % pixels
    print type(pixels)
    lamp.color_array(strip, pixels)
    return len(pixels)


public = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        'public'))

class PlampNamespace(BaseNamespace):
    _registry = {}

    def initialize(self):
        self._registry[id(self)] = self
        print "co-nekt"
        self.emit('connect')
        self.nick = None
        print("COLOR: [%s, %s, %s]" % (R, G, B)) 
        self.emit('color_wiped', [R, G, B, 0])      
 
    def disconnect(self, *args, **kwargs):
        print "disco-nekt"
        super(PlampNamespace, self).disconnect(*args, **kwargs)

    def on_color_wipe(self, str):
        w = color_wipe(str)
        if w:
            self._broadcast('color_wiped', w)
        
    def on_color_array(self, str):
        count = color_array(str)
        self._broadcast('color_arrayed',{'count':count})

    def _broadcast(self, event, message):
        for s in self._registry.values():
            s.emit(event, message)


def plamp(environ, start_response):
    """
    This is the main routing
    """
    print "plamp pathinfo %s" % environ['PATH_INFO']
    if environ['PATH_INFO'].startswith('/socket.io'):
        return socketio_manage(environ, { '/plamp': PlampNamespace })
    else:
        if environ['REQUEST_METHOD'] == 'GET':
            return serve_file(environ, start_response)
        if environ['REQUEST_METHOD'] == 'POST':
            if environ['PATH_INFO'] == "/color_wipe":
                return post_color_wipe(environ, start_response)
            if environ['PATH_INFO'] == "/color_array":
                return post_color_array(environ, start_response)
            return api_not_found(environ, start_response)


def api_not_found(environ, start_response):
    start_response('404 NOT FOUND', [])
    r = 'route "%s" not found' % environ['PATH_INFO'] 
    yield r

def get_headers():
    r = [ ('Content-Type', 'application/json'),
    # ('Access-Control-Allow-Origin', '*'),
    # ('Access-Control-Allow-Methods', 'POST, GET, PUT, PATCH, DELETE, OPTIONS'),
    # ('Access-Control-Allow-Headers', 'Content-Type, X-Requested-With'),
    # ('Access-Control-Max-Age', '1728000'),
    ]
    return r

def post_color_wipe(environ, start_response):
    dataStr = environ['wsgi.input'].read()
    color_wipe(dataStr)
    start_response('200 OK', get_headers())
    r = {"color_wipe": data}
    yield r

def post_color_array(environ, start_response):
    print("color_array")
    dataStr = environ['wsgi.input'].read()
    color_array(dataStr)
    start_response('200 OK', [('Content-Type', 'text/html')])
    r = '{"count": 0}'
    yield r


def serve_file(environ, start_response):
    f = environ['PATH_INFO']
    if f == '/':
        f= '/index.html'
    path = os.path.normpath(
        os.path.join(public, f.lstrip('/')))
    print "serve file: %s" % path
    assert path.startswith(public), path
    if os.path.exists(path):
        start_response('200 OK', [('Content-Type', 'text/html')])
        with open(path) as fp:
            while True:
                chunk = fp.read(4096)
                if not chunk: break
                yield chunk
    else:
        start_response('404 NOT FOUND', [])
        yield 'File not found'

sio_server = SocketIOServer(
    ('', port), plamp, 
    policy_server=False)
sio_server.serve_forever()
