# -*- coding: utf-8 -*-

from email2SMS_idle import local_settings
from datetime import date
import datetime, logging, json, time, gmail, traceback

# Get an instance of a logger
logger = logging.getLogger(__name__)

class GmailPolling():

    gmail_imap = None

    def __init__(self):
        self.init_connection()
        return None

    def init_connection(self):
        """Function to start an IMAP connection"""
        # https://github.com/charlierguo/gmail
        self.gmail_imap = gmail.login(local_settings.c1, local_settings.c2)
        return True

    def idle_callback(self):
        """Function performed when idle notify new emails"""
        try:
            # logger.info("check email")
            # self.mail2sms()
            self.mail2sms_test()
        # except self.gmail_imap.imap.abort, e:
        except BaseException as e:
            # probabilmente un timeout della connessione, provo a riconnettermi (logout + nuova connessione)
            logger.error("@@ Errore in read_email_and_send_sms:")
            logger.error("msg: " + str(e.message))
            logger.error("args: " + str(e.args))
            logger.error("class: " + str(e.__class__.__name__))
            logger.error("trace: " + str(traceback.format_exc()))
            # self.gmail_imap.logout()
            # self.init_connection()
            # TODO: mi riconnetto e provo a rifare la lettura di eventuali nuove email
        return True

    def mail2sms(self):
        """List of unread email"""
        # prelevo l'elenco di email in base a determinati criteri
        # emails = self.gmail_imap.inbox().mail(on=date.today(), unread=True, sender=local_settings.sender)
        emails = self.gmail_imap.inbox().mail(on=date.today(), unread=True)
        for email in emails:
            # prelevo i dati per ogni singola email (oggetto, testo, ...)
            email.fetch()
            # email subject
            email_subject = email.subject
            # se c'è un allarme o un allarme è stato disattivato
            if email_subject.find("Allarme") > -1 or email_subject.find("Fin.All.") > -1:
                # marco la mail come letta
                email.read()
                # invio l'sms
                self.send_sms(text=email_subject)

        # fix per far riscaricare i messaggi della inbox, la libreria cachava tutto e se
        # arrivava un nuovo messaggio non veniva tirato giù, ho solo resettato alcuni campi
        self.gmail_imap.mailboxes = {}
        self.gmail_imap.current_mailbox = None
        self.gmail_imap.fetch_mailboxes()
        return True

    def mail2sms_test(self):
        """List of unread email"""
        # prelevo l'elenco di email in base a determinati criteri
        emails = self.gmail_imap.inbox().mail(on=date.today(), unread=True)
        for email in emails:
            # prelevo i dati per ogni singola email (oggetto, testo, ...)
            email.fetch()
            # email subject
            email_subject = email.subject
            # se c'è un allarme o un allarme è stato disattivato
            # marco la mail come letta
            email.read()
            logger.info("oggetto email: " + str(email_subject))

        # fix per far riscaricare i messaggi della inbox, la libreria cachava tutto e se
        # arrivava un nuovo messaggio non veniva tirato giù, ho solo resettato alcuni campi
        self.gmail_imap.mailboxes = {}
        self.gmail_imap.current_mailbox = None
        self.gmail_imap.fetch_mailboxes()
        return True

    def send_sms(self, text):
        """Function to send an sms"""
        client = nexmo.Client(key=local_settings.nexmo_key, secret=local_settings.nexmo_secret)
        # invio l'sms ad ogni numero telefonico
        for sms_number in local_settings.notify_numbers:
            logger.info("invio a: " + str(sms_number) + " -> testo: " + str(text))
            response = client.send_message({'from': local_settings.from_name, 'to': "+39" + str(sms_number), 'text': text})
            response = response['messages'][0]
            if response['status'] == '0':
              logger.info('Sent message ', response['message-id'])
              logger.info('Remaining balance is ', response['remaining-balance'])
            else:
              logger.error('SMS sending error: ', response['error-text'])
        return True

    """
    def periodic_task_crashed(self, exception):
        #""Loop error""
        logger.error("Errore nel loop (fermare l'app, rilanciarla e capire il misfatto): " + str(exception))
        # TODO: mandare sms e email per notificare l'errore
        return True
    """
