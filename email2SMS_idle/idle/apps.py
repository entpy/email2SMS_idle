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
        try:
            GmailPolling_obj = GmailPolling()
            GmailPolling_obj.gmail_imap.inbox()
            # Thread per avviare la funzione idle
            idler = Idler(GmailPolling_obj.gmail_imap.imap, GmailPolling_obj)
            idler.start()
            # watchdog del processo
            background_loop = task.LoopingCall(idler.is_alive)
            # utilizzando Crochet posso mettere in background il loop
            # (altrimenti bloccante con Twisted) e permettere all'app di
            # Django di avviarsi
            # avvio del watchdog del processo (subito e quindi ogni x secondi)
            crochet_reactor = background_loop.start(60, now=True)
            # callback in caso di terminazione loop (CTRL^C) -> effettuo shutdown di idle
            reactor.addSystemEventTrigger("after", "shutdown", idler.kill_thread)
            # in caso di errore nel loop chiamo questa callback
            crochet_reactor.addErrback(idler.periodic_task_crashed)
        except BaseException as e:
            logger.error("Eccezione (fermare l'app, rilanciarla e capire il misfatto): " + str(e))
            idler.kill_thread()
        return True
