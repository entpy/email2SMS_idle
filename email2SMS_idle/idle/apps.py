# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function
from django.apps import AppConfig
from idle import Idler
from polling import GmailPolling
from twisted.internet import task
from twisted.internet import reactor
from crochet import setup
import logging, time

# Get an instance of a logger
logger = logging.getLogger(__name__)

setup()
class IdleConfig(AppConfig):
    name = 'idle'

    def ready(self):
        logger.info("email2SMS_idle avviata...")
        self.init_idle()
        return True

    def init_idle(self):
        #""Function to init imap idle""
        # Had to do this stuff in a try-finally, since some testing 
        # went a little wrong.....
        try:
            GmailPolling_obj = GmailPolling()
            GmailPolling_obj.gmail_imap.inbox()
            # Start the Idler thread
            idler = Idler(GmailPolling_obj.gmail_imap.imap, GmailPolling_obj)
            idler.start()
            # Because this is just an example, exit after 1 minute.
            # time.sleep(60*60*24)
            # watchdog del processo
            """
            l = task.LoopingCall(idler.is_alive)
            l.start(1.0) # call every sixty seconds
            reactor.addSystemEventTrigger("after", "shutdown", idler.kill_thread, reactor)
            reactor.run()
            """
            background_loop = task.LoopingCall(idler.is_alive)
            # avvia il watchdog subito e quindi ogni 60 secondi
            crochet_reactor = background_loop.start(60, now=True)
            # callback in caso di errore
            reactor.addSystemEventTrigger("after", "shutdown", idler.kill_thread)
            crochet_reactor.addErrback(idler.periodic_task_crashed)
            # reactor.addSystemEventTrigger("after", "shutdown", idler.kill_thread)
        except BaseException as e:
            logger.error("Eccezione (fermare l'app, rilanciarla e capire il misfatto): " + str(e))
            idler.kill_thread()

        return True
