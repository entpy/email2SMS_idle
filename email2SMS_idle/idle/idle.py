# -*- coding: utf-8 -*-

from threading import *
from datetime import date
import logging, email, traceback

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
        self.error = None # flag degli errori
        # Starting an unending loop here
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
                result, arg, exc = args
                if result is None:
                    logger.error("There was an error during IDLE: " + str(exc))
                    logger.error("trace: " + str(traceback.format_exc()))
                    self.error = exc
                    self.event.set()
                elif not self.event.isSet():
                    self.needsync = True
                    self.event.set()
            # Do the actual idle call. This returns immediately, 
            # since it's asynchronous.
            self.M.idle(callback=callback)
            # TODO
            """
            # disconnessione, tento di recuperare riconettendomi
            self.gmail.gmail_imap.logout()
            self.gmail.init_connection()
            # assegno la nuova connessione al thread per poter rifare l'idle
            self.M = self.gmail.gmail_imap.imap
            # rieffettuo l'idle
            self.M.idle(callback=callback)
            """

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

            if self.error:
                # gestisco l'eccezione
                # self.manage_exception(self.error)
                try:
                    raise self.error
                except self.M.abort as e:
                    logger.error("errore di abort della connessione di imap")
                    # tento il recupero della connessione
                    self.idle_recovery()
                    # forzo una ri-sincronizzazione
                    self.dosync()
                    # pulisco lo status del thread e il flag degli errori
                    self.event.clear()
                    self.error = None
 
    # The method that gets called when a new email arrives. 
    def dosync(self):
        """
        http://stackoverflow.com/questions/16622132/imaplib2-imap-gmail-com-handler-bye-response-system-error
        """
        logger.info("nuova/e email!")
        try:
            self.gmail.idle_callback()
        except BaseException as e:
            logger.error("Errore in dosync: " + str(e))
            logger.error("trace: " + str(traceback.format_exc()))
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

    def idle_recovery(self):
        """Try to recover an idle session"""
        # mi disconnetto e riconnetto via imap al provider
        logger.info("Tento di recuperare la connessione")
        self.gmail.gmail_imap.logout()
        self.gmail.init_connection()
        # assegno la nuova connessione al thread per poter rifare l'idle
        self.M = self.gmail.gmail_imap.imap
        return True

"""
vecchia callback
def callback(args):
    if not self.event.isSet():
        self.needsync = True
        self.event.set()
"""

"""
From imaplib2s documentation:

If 'callback' is provided then the command is asynchronous, so after
the command is queued for transmission, the call returns immediately
with the tuple (None, None).
The result will be posted by invoking "callback" with one arg, a tuple:
callback((result, cb_arg, None))
or, if there was a problem:
callback((None, cb_arg, (exception class, reason)))

This means your call back needs to look at it's arguments:

            def callback(args):
                result, arg, exc = args
                if result is None:
                    print("There was an error during IDLE:", str(exc))
                    self.error = exc
                    self.event.set()
                else:
                    self.needsync = True
                    self.event.set()
"""
