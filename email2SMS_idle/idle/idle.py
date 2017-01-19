# -*- coding: utf-8 -*-

from threading import *
from datetime import date
import logging, email

# Get an instance of a logger
logger = logging.getLogger(__name__)

# https://gist.github.com/jexhson/3496039/
# This is the threading object that does all the waiting on the event
class Idler(object):
    def __init__(self, conn, gmail):
        logger.info("@@ IDLE init @@")
        self.thread = Thread(target=self.idle)
        # questo killa il thread quando viene killata l'app (ma senza tenere conto di eventuali procedure di shutdown)
        # self.thread.setDaemon(True)
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
        logger.info("@@ join thread IDLE @@")
        self.thread.join()
 
    def idle(self):
        # Starting an unending loop here
        try:
            while True:
                logger.info("metto in attesa con il comando IDLE")
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
                logger.info("IDLE in attesa di nuove email")
                self.event.wait()
                logger.info("dovrebbero esserci nuove email")
                # Because the function sets the needsync variable,
                # this helps escape the loop without doing 
                # anything if the stop() is called. Kinda neat 
                # solution.
                if self.needsync:
                    self.event.clear()
                    self.dosync()
        except BaseException as e:
            logger.error("Errore nel comando IDLE: " + str(e))
            self.kill_thread()
 
    # The method that gets called when a new email arrives. 
    def dosync(self):
        logger.info("nuova/e email!")
        try:
            self.gmail.get_unread_email_test()
        except BaseException as e:
            logger.error("Errore in dosync: " + str(e))
            self.kill_thread()
        return True

    def is_alive(self):
        """Function to check if process is alive"""
        logger.info("IDLE is alive")
        return True

    def periodic_task_crashed(self, exception):
        """Callback to manage Twisted loop error"""
        logger.error("Errore nel loop (fermare l'app, rilanciarla e capire il misfatto): " + str(exception))
        # XXX: mandare sms e email per notificare l'errore
        return True

    def kill_thread(self):
        """Function to manage Twisted loop shutdown (CTRL^C)"""
        logger.error("Inizio procedura di shutdown del loop...")
        # Clean up.
        self.stop()
        self.join()
        # This is important!
        self.gmail.gmail_imap.logout()
        logger.info("Fine procedura di shutdown del loop")
        return True
