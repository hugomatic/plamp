#!/usr/bin/env python

import os

from socketio import socketio_manage
from socketio.server import SocketIOServer
from socketio.namespace import BaseNamespace
import lamp

port = 80
led_count = 3 * 64


strip = lamp.create_strip(led_count)

def color_wipe(str):
    print "on color_wipe", str
    data = eval(str)
    r = int(data[0])
    g = int(data[1])
    b = int(data[2])
    w = int(data[3])
    lamp.color_wipe(strip, r, g, b, w)
    return  data
        
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
        self.emit('connect')
        self.nick = None

    def disconnect(self, *args, **kwargs):
        print "disco-nekt"
        super(PlampNamespace, self).disconnect(*args, **kwargs)

    def on_color_wipe(self, str):
        w = color_wipe(str)
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
    print "PATHate: %s" % path
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
