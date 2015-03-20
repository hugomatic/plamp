#!/usr/bin/env python

import os

from socketio import socketio_manage
from socketio.server import SocketIOServer
from socketio.namespace import BaseNamespace
import lamp

port = 80
led_count = 64


strip = lamp.create_strip(led_count)

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
        if self.nick:
            self._broadcast('exit', self.nick)
        del self._registry[id(self)]
        super(PlampNamespace, self).disconnect(*args, **kwargs)

    def on_color_wipe(self, m):
        print "on color_wipe", m
        data = eval(m)
        r = int(data[0])
        g = int(data[1])
        b = int(data[2])
        w = int(data[3])
        lamp.color_wipe(strip, r, g, b, w)
        self._broadcast('color_wiped', data)

    def on_color_array(self, data):
        print "on color array"
        print "data %s" % data
        pixels = eval(data)
        print "PIXELS %s" % pixels
        print type(pixels)
        lamp.color_array(strip, pixels)
        self._broadcast('color_arrayed',{'count':len(pixels)})

    def _broadcast(self, event, message):
        for s in self._registry.values():
            s.emit(event, message)


def plamp(environ, start_response):
    print "plamp pathinfo %s" % environ['PATH_INFO']
    if environ['PATH_INFO'].startswith('/socket.io'):
        return socketio_manage(environ, { '/plamp': PlampNamespace })
    else:
        return serve_file(environ, start_response)

def serve_file(environ, start_response):
    print "serve file"
    print "%s" % environ
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
