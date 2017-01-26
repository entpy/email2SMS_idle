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
        self.error_count = 0
        self.enable_error_debug = False
 
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
                logger.error("Chiamo la callback di idle")
                result, arg, exc = args
                self.error_count += 1

                # per debuggare l'errore di abort
                if self.error_count > 1 and self.enable_error_debug:
                    exc = self.M.abort('connection closed')
                    result = None

                if result is None:
                    logger.error("There was an error during IDLE: " + str(exc))
                    # logger.error("trace: " + str(traceback.format_exc()))
                    self.error = exc
                    self.event.set()
                elif not self.event.isSet():
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

            # gestisco alcuni errori, tra i quali il timeout della connessione
            if self.error:
                try:
                    raise self.error
                except self.M.abort as e:
                    logger.info("1 errore di abort della connessione di imap (es timeout)")
                    # tento il recupero della connessione
                    self.idle_recovery()
                    # forzo una ri-sincronizzazione
                    logger.info("1 self.needsync = True")
                    self.needsync = True
                    # pulisco il flag degli errori
                    logger.info("1 self.error = None")
                    self.error = None
                finally:
                    logger.info("connessione recuperata")
                    logger.info("needsync? " + str(self.needsync))
            # Because the function sets the needsync variable,
            # this helps escape the loop without doing 
            # anything if the stop() is called. Kinda neat 
            # solution.
            if self.needsync:
                self.event.clear()
                self.dosync()

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
        logger.info("2 Tento di recuperare la connessione")

        try:
            logger.info("2 self.gmail.gmail_imap.logout()")
            self.gmail.gmail_imap.logout()
        except BaseException as e:
            logger.error("2 ERRORE IN self.gmail.gmail_imap.logout(): " + str(e))
        else:
            logger.info("2 self.gmail.init_connection()")
            self.gmail.init_connection()
            # assegno la nuova connessione al thread per poter rifare l'idle
            logger.info("2 self.M = self.gmail.gmail_imap.imap")
            self.M = self.gmail.gmail_imap.imap
            # resetto il flag di debug per gli errori
            self.error_count = 0
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
