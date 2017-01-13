# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function
from django.apps import AppConfig
from idle import Idler
from polling import GmailPolling
import logging, time

# Get an instance of a logger
logger = logging.getLogger(__name__)

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
        except Exception, e:
            logger.error("Eccezione (fermare l'app, rilanciarla e capire il misfatto): " + str(e))
            # Clean up.
            idler.stop()
            idler.join()
            # This is important!
            GmailPolling_obj.gmail_imap.logout()
            logger.info("IDLE terminato")

        return True
