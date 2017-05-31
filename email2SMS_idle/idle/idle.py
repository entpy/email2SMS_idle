# -*- coding: utf-8 -*-

from threading import *
from datetime import date
from django.core.mail import send_mail
from email2SMS_idle import local_settings
import logging, email, traceback, time

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
        self.enable_error_debug = False
        self.error = None # flag degli errori
 
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
                    logger.info("connessione recuperata")

                    # XXX
                    # invio una email di notifica
                    # rimuovere anche perchè l'invio
                    # email occupa tempo
                    self.send_admin_email(str(local_settings.subject_app_name) + ": errore di abort della connessione di imap (es timeout)", str(e) + "<br /><br /><b>Connessione recuperata</b>")
                except BaseException as e:
                    logger.error("1 errore nel recupero della connessione: " + str(e))
                    # invio una mail di notifica errore all'amministratore
                    self.send_admin_email(str(local_settings.subject_app_name) + ": errore nel recupero della connessione", str(e))
                finally:
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
            error_traceback = str(traceback.format_exc())
            logger.error("Errore in dosync: " + str(e))
            logger.error("trace: " + error_traceback)
            # invio una mail di notifica errore all'amministratore
            self.send_admin_email(str(local_settings.subject_app_name) + ": errore in dosync", error_traceback)
            try:
                # tento il recupero della connessione e riprovo
                # a prelevare le email da leggere
                logger.error("setto un timeout per evitare troppe riconnessioni in poco tempo")
                time.sleep(10) # XXX: vediamo se è questione di troppe riconnessioni in poco tempo
                self.idle_recovery()
                self.gmail.idle_callback()
            except BaseException as e:
                error_traceback = str(traceback.format_exc())
                logger.error("Doppio errore in dosync: " + str(e))
                logger.error("trace: " + error_traceback)
                # invio una mail di notifica errore all'amministratore
                self.send_admin_email(str(local_settings.subject_app_name) + ": doppio errore in dosync", error_traceback)
                # troppi errori, killo il thread
                self.kill_thread()
        return True

    def is_alive(self):
        """Function to check if process is alive"""
        logger.info("IDLE is alive")

        # per simulare il termine della connessione
        if self.enable_error_debug:
            self.gmail.gmail_imap.imap.Terminate = True
            self.gmail.gmail_imap.imap._handler()
        return True

    def periodic_task_crashed(self, exception):
        """Callback to manage Twisted loop error"""
        logger.error("Errore nel loop (fermare l'app, rilanciarla e capire il misfatto): " + str(exception))
        # invio una mail di notifica errore all'amministratore
        self.send_admin_email(str(local_settings.subject_app_name) + ": Errore nel loop di Twisted", str(exception))
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
        finally:
            time.sleep(2) # XXX: setto una sleep per evitare la riconnessione subito
            logger.info("2 self.gmail.init_connection()")
            self.gmail.init_connection()
            # assegno la nuova connessione al thread per poter rifare l'idle
            logger.info("2 self.M = self.gmail.gmail_imap.imap")
            self.M = self.gmail.gmail_imap.imap
        return True

    def send_admin_email(self, subject, content):
        """Function to send an info email to administrator"""
        return_var = False
        if subject and content:
            logger.info("send_admin_email() -> invio una email di notifica a: " + str(local_settings.admin_email_to))
            send_mail(subject, content, str(local_settings.admin_email_from), local_settings.admin_email_to, fail_silently=True)
            return_var = True
        return return_var

"""
From imaplib2s documentation:

If 'callback' is provided then the command is asynchronous, so after
the command is queued for transmission, the call returns immediately
with the tuple (None, None).
The result will be posted by invoking "callback" with one arg, a tuple:
callback((result, cb_arg, None))
or, if there was a problem:
callback((None, cb_arg, (exception class, reason)))

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
