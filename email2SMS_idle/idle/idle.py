# -*- coding: utf-8 -*-

from threading import *
from datetime import date
import logging, email

# Get an instance of a logger
logger = logging.getLogger(__name__)

# https://gist.github.com/jexhson/3496039/
# This is the threading object that does all the waiting on 
# the event
class Idler(object):
    def __init__(self, conn, gmail):
        logger.info("@@ IDLE init @@")
        self.thread = Thread(target=self.idle)
        self.M = conn
        self.event = Event()
        self.gmail = gmail
 
    def start(self):
        self.thread.start()
 
    def stop(self):
        # This is a neat trick to make thread end. Took me a 
        # while to figure that one out!
        logger.info("@@ stop thread IDLE @@")
        self.event.set()
 
    def join(self):
        self.thread.join()
 
    def idle(self):
        # Starting an unending loop here
        while True:
            logger.info("check")
            # This is part of the trick to make the loop stop 
            # when the stop() command is given
            if self.event.isSet():
                return
            self.needsync = False
            # A callback method that gets called when a new 
            # email arrives. Very basic, but that's good.
            def callback(args):
                if not self.event.isSet():
                    self.needsync = True
                    self.event.set()
            # Do the actual idle call. This returns immediately, 
            # since it's asynchronous.
            self.M.idle(callback=callback)
            # This waits until the event is set. The event is 
            # set by the callback, when the server 'answers' 
            # the idle call and the callback function gets 
            # called.
            self.event.wait()
            # Because the function sets the needsync variable,
            # this helps escape the loop without doing 
            # anything if the stop() is called. Kinda neat 
            # solution.
            if self.needsync:
                self.event.clear()
                self.dosync()
 
    # The method that gets called when a new email arrives. 
    def dosync(self):
        logger.info("Nuova email!")
        self.gmail.get_unread_email_test()

        return True
