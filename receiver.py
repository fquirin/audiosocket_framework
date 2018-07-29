#!/usr/bin/env python

from __future__ import absolute_import, print_function

import argparse
import ConfigParser as configparser
import io
import logging
import os
import sys
import time
from ConfigParser import SafeConfigParser as ConfigParser
from logging import debug, info

import tornado.ioloop
import tornado.websocket
import tornado.httpserver
import tornado.template
import tornado.web
# import webrtcvad
from tornado.web import url
import json

#Only used for record function
import datetime
import wave

CLIP_MIN_MS = 200  # 200ms - the minimum audio clip that will be used
MAX_LENGTH = 8000  # Max length of a sound clip for processing in ms
SILENCE = 20  # How many continuous frames of silence determine the end of a phrase

# Constants:
BYTES_PER_FRAME = 640  # Bytes in a frame
MS_PER_FRAME = 20  # Duration of a frame in ms

CLIP_MIN_FRAMES = CLIP_MIN_MS // MS_PER_FRAME

# Global variables
conns = {}

# This should be least-specific -> most-specific:
CONFIG_PATHS = [
    "/etc/app.conf",
    os.path.expanduser("~/.app.conf"),
    "./app.conf",
]



class BufferedPipe(object):
    def __init__(self, max_frames, sink):
        """
        Create a buffer which will call the provided `sink` when full.

        It will call `sink` with the number of frames and the accumulated bytes when it reaches
        `max_buffer_size` frames.
        """
        self.sink = sink
        self.max_frames = max_frames

        self.count = 0
        self.payload = b''

    def append(self, data, cli):
        """ Add another data to the buffer. `data` should be a `bytes` object. """

        self.count += 1
        self.payload += data

        if self.count == self.max_frames:
            self.process(cli)

    def process(self, cli):
        """ Process and clear the buffer. """

        self.sink(self.count, self.payload, cli)
        self.count = 0
        self.payload = b''


class Processor(object):
    def __init__(self, path):
        self.path = path
    def process(self, count, payload, cli):
        if count > CLIP_MIN_FRAMES:  # If the buffer is less than CLIP_MIN_MS, ignore it
            info('Processing {} frames from {}'.format(count, cli))
            fn = "{}rec-{}-{}.wav".format(self.path, cli, datetime.datetime.now().strftime("%Y%m%dT%H%M%S"))
            output = wave.open(fn, 'wb')
            output.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))  # nchannels, sampwidth, framerate, nframes, comptype, compname
            output.writeframes(payload)
            output.close()
            info('File written {}'.format(fn))
            conn = conns[cli]
            conn.write_message('fFinal result, file written')
        else:
            info('Discarding {} frames'.format(str(count)))    
    def playback(self, content, cli):
        frames = len(content) // 640
        info("Playing {} frames to {}".format(frames, cli))
        conn = conns[cli]
        pos = 0
        for x in range(0, frames + 1):
            newpos = pos + 640
            debug("writing bytes {} to {} to socket for {}".format(pos, newpos, cli))
            data = content[pos:newpos]
            conn.write_message(data, binary=True)
            time.sleep(0.018)
            pos = newpos

			
class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello world!")

class WSHandler(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
	    return True
		
    def initialize(self, processor):
        # Create a buffer which will call `process` when it is full:
        self.frame_buffer = BufferedPipe(MAX_LENGTH // MS_PER_FRAME, processor)
        # Setup the Voice Activity Detector
        self.tick = None
        self.cli = None
        self.frames = None
        # self.vad = webrtcvad.Vad()
        # self.vad.set_mode(1)  # Level of sensitivity
		
    def open(self):
        info("client connected")
        # Add the connection to the list of connections
        self.tick = 0
        self.frames = 0
        # TODO: handle multiple users
        self.cli = "onlyonearound"
        conns[self.cli] = self
		
    def on_message(self, message):
        # Check if message is Binary or Text
        info("got message, type: " + type(message).__name__)
        if type(message) == unicode:
            self.write_message('You sent unicode: ' + message)
            info("data: " + message)
        elif type(message) == str:
            # self.write_message('You sent str: ' + message)
            # info("data: " + message)
            self.frames += 1
            info(" {}".format(self.frames))
            if self.frames == 30:
                self.write_message('iIntermediate result')
            elif self.frames == 60:
                self.write_message('iFinished listening, processing ...')
                self.frame_buffer.append(message, self.cli)
                self.frame_buffer.process(self.cli)
            else:
                self.frame_buffer.append(message, self.cli)
            # if self.vad.is_speech(message, 16000):
                # debug ("SPEECH from {}".format(self.cli))
                # self.tick = SILENCE
                # self.frame_buffer.append(message, self.cli)
            # else:
                # debug("Silence from {} TICK: {}".format(self.cli, self.tick))
                # self.tick -= 1
                # if self.tick == 0:
                    # self.frame_buffer.process(self.cli)  # Force processing and clearing of the buffer
        else:
            info(message)
            # Here we should be extracting the meta data that was sent and attaching it to the connection object
            # data = json.loads(message)
            # self.cli = data['cli']
            # conns[self.cli] = self
            self.write_message('ok')

    def on_close(self):
        # Remove the connection from the list of connections
        del conns[self.cli]
        info("client disconnected")


class Config(object):
    def __init__(self, specified_config_path):
        config_paths = list(CONFIG_PATHS)
        if specified_config_path is not None:
            config_paths = CONFIG_PATHS + [specified_config_path]

        config = ConfigParser()
        if not config.read(config_paths):
            print(
                "No config file found at the following locations: "
                + "".join('\n    {}'.format(cp) for cp in config_paths),
                file=sys.stderr,
            )
            # sys.exit(1)
            self.port = 20741
            self.path = "./recordings/"
			
        # Validate config:
        try:
            #self.host = config.get("app", "host")
            #self.event_url = "http://{}/event".format(self.host)
            self.port = config.getint("app", "port")
            self.path = config.get("app", "path")
        except configparser.Error as e:
            print("Configuration Error:", e, file=sys.stderr)
            sys.exit(1)


def main(argv=sys.argv[1:]):
    try:
        ap = argparse.ArgumentParser()
        ap.add_argument("-v", "--verbose", action="count")
        ap.add_argument("-c", "--config", default=None)

        args = ap.parse_args(argv)

        logging.basicConfig(
            level=logging.INFO if args.verbose < 1 else logging.DEBUG,
            format="%(levelname)7s %(message)s",
        )

        config = Config(args.config)
        
        #Pass any config for the processor into this argument.
        processor = Processor(config.path).process

        application = tornado.web.Application([
			url(r'/ping', MainHandler),
            url(r'/socket', WSHandler, dict(processor=processor))
        ])

        http_server = tornado.httpserver.HTTPServer(application)
        http_server.listen(config.port)
        info("Running on port %s", config.port)
        tornado.ioloop.IOLoop.instance().start()		
    except KeyboardInterrupt:
        pass  # Suppress the stack-trace on quit


if __name__ == "__main__":
    main()
