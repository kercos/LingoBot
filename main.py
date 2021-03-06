# -*- coding: utf-8 -*-

# import json
import json
import logging
import urllib
import urllib2
import requests
import datetime
from datetime import datetime
from time import sleep
import re

# standard app engine imports
from google.appengine.api import urlfetch
from google.appengine.ext import ndb
from google.appengine.ext import deferred

import key
import person
from person import Person
import utility
import jsonUtil
import string

import webapp2
import exercise_synonim, exercise_intruder
import random
#from ConversionGrid import GRID


########################
WORK_IN_PROGRESS = False
########################

STATES = {
    0:   'Initial Screen',
    1:   'Synonim Game',
    2:   'Intruder Game',
}

CANCEL = u'\U0000274C'.encode('utf-8')
CHECK = u'\U00002705'.encode('utf-8')
LEFT_ARROW = u'\U00002B05'.encode('utf-8')
UNDER_CONSTRUCTION = u'\U0001F6A7'.encode('utf-8')
FROWNING_FACE = u'\U0001F641'.encode('utf-8')
BULLET_RICHIESTA = '🔹'
BULLET_OFFERTA = '🔸'
BULLET_POINT = '🔸'

BUTTON_SYNONIM_GAME = "🖇 SYNONIM GAME"
BUTTON_INTRUDER_GAME = "🐸 INTRUDER GAME"
BUTTON_ACCEPT = CHECK + " ACCEPT"
BUTTON_CONFIRM = CHECK + " CONFIRM"
BUTTON_ABORT = CANCEL + " ABORT"
BUTTON_BACK = "⬅ BACK"
BUTTON_NEXT = "➡ NEXT"
BUTTON_EXIT = CANCEL + " EXIT"
BUTTON_NEXT_SENTENCE = "➡ NEXT SENTENCE"
BUTTON_NO_INTRUDER = "NO INTRUDER"

BUTTON_INFO = "ℹ INFO"

# ================================
# ================================
# ================================


ISTRUZIONI = UNDER_CONSTRUCTION + "*Instruction* LingoBot to complete..."
INFO_TEXT = UNDER_CONSTRUCTION +  "*INFO* LingoBot to complete..."


# ================================
# ================================
# ================================


def broadcast(msg, restart_user=False, sender_id=None):
    qry = Person.query().order(-Person.last_mod)
    disabled = 0
    count = 0
    for p in qry:
        if p.enabled:
            count += 1
            tell(p.chat_id, msg, sleepDelay=True)
            if restart_user:
                restart(p)
        else:
            disabled += 1
    if sender_id:
        enabledCount = qry.count() - disabled
        msg_debug = 'Messaggio inviato a ' + str(qry.count()) + ' persone.\n' + \
                    'Messaggio ricevuto da ' + str(enabledCount) + ' persone.\n' + \
                    'Persone disabilitate: ' + str(disabled)
        tell(sender_id, msg_debug)

def getInfoCount():
    c = Person.query().count()
    msg = "Attualmente siamo in " + str(c) + " persone iscritte a BancaTempoBot! " + \
          "Vogliamo crescere assieme! Invita altre persone ad aunirsi!"
    return msg


def tell_masters(msg):
    for id in key.MASTER_CHAT_ID:
        tell(id, msg)

def tellAdministrators(msg):
    for id in key.AMMINISTRATORI_ID:
        tell(id, msg)


def tell(chat_id, msg, kb=None, markdown=True, inlineKeyboardMarkup=False,
         one_time_keyboard=True, sleepDelay=False):
    replyMarkup = {
        'resize_keyboard': True,
        'one_time_keyboard': one_time_keyboard
    }
    if kb:
        if inlineKeyboardMarkup:
            replyMarkup['inline_keyboard'] = kb
        else:
            replyMarkup['keyboard'] = kb
    try:
        data = {
            'chat_id': chat_id,
            'text': msg,
            'disable_web_page_preview': 'true',
            'parse_mode': 'Markdown' if markdown else '',
            'reply_markup': json.dumps(replyMarkup),
        }
        resp = requests.post(key.BASE_URL + 'sendMessage', data)
        logging.info('Response: {}'.format(resp.text))
        #logging.info('Json: {}'.format(resp.json()))
        respJson = json.loads(resp.text)
        success = respJson['ok']
        if success:
            if sleepDelay:
                sleep(0.1)
            return True
        else:
            status_code = resp.status_code
            error_code = respJson['error_code']
            description = respJson['description']
            if error_code == 403:
                # Disabled user
                p = person.getPersonByChatId(chat_id)
                p.setEnabled(False, put=True)
                logging.info('Disabled user: ' + p.getUserInfoString())
            elif error_code == 400 and description == "INPUT_USER_DEACTIVATED":
                p = person.getPersonByChatId(chat_id)
                p.setEnabled(False, put=True)
                debugMessage = '❗ Input user disactivated: ' + p.getUserInfoString()
                logging.debug(debugMessage)
                tell(key.FEDE_CHAT_ID, debugMessage, markdown=False)
            else:
                debugMessage = '❗ Raising unknown err in tell() when sending msg={} kb={}.' \
                          '\nStatus code: {}\nerror code: {}\ndescription: {}.'.format(
                    msg, kb, status_code, error_code, description)
                logging.error(debugMessage)
                tell(key.FEDE_CHAT_ID, debugMessage, markdown=False)
    except:
        report_exception()

# ================================
# SEND WAITING ACTION
# ================================

def sendWaitingAction(chat_id, action_type='typing', sleep_time=1.0):
    data = {
        'chat_id': chat_id,
        'action': action_type,
    }
    requests.post(key.BASE_URL + 'sendChatAction', data=data)
    if sleep_time:
        sleep(sleep_time)


# ================================
# RESTART
# ================================
def restart(p, msg=None):
    if msg:
        tell(p.chat_id, msg)
    redirectToState(p, 0)


# ================================
# SWITCH TO STATE
# ================================
def redirectToState(p, new_state, **kwargs):
    if p.state != new_state:
        logging.debug("In redirectToState. current_state:{0}, new_state: {1}".format(str(p.state),str(new_state)))
        p.setState(new_state)
    repeatState(p, **kwargs)

# ================================
# REPEAT STATE
# ================================
def repeatState(p, **kwargs):
    methodName = "goToState" + str(p.state)
    method = possibles.get(methodName)
    if not method:
        tell(p.chat_id, "Si è verificato un problema (" + methodName +
              "). Segnalamelo mandando una messaggio a @kercos" + '\n' +
              "Ora verrai reindirizzato/a nella schermata iniziale.")
        restart(p)
    else:
        method(p, **kwargs)


# ================================
# GO TO STATE 0: Initial Screen
# ================================

def goToState0(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    if giveInstruction:
        reply_txt = 'Hi {}, press *{}* or *{}* if you want to play!'.format(
            p.getName(), BUTTON_SYNONIM_GAME, BUTTON_INTRUDER_GAME)

        kb = [
            [BUTTON_SYNONIM_GAME],
            [BUTTON_INTRUDER_GAME],
            [BUTTON_INFO]
        ]

        tell(p.chat_id, reply_txt, kb)
    else:
        if input == '':
            tell(p.chat_id, "Not a valid input.")
        elif input == BUTTON_SYNONIM_GAME:
            first_time_instructions = utility.unindent(
                """
                Let’s train your vocabulary! Can you find a word with the same meaning?
                You will see a series of sentences with certain words highlighted.
                Which words describe the highlighted parts best?
                """
            )
            tell(p.chat_id, first_time_instructions)
            sendWaitingAction(p.chat_id, sleep_time=1)
            redirectToState(p, 1)
        elif input == BUTTON_INTRUDER_GAME:
            first_time_instructions = utility.unindent(
                """
                Let’s find the intruder! 🐸
                """
            )
            tell(p.chat_id, first_time_instructions)
            sendWaitingAction(p.chat_id, sleep_time=1)
            redirectToState(p, 2)
        elif input == BUTTON_INFO:
            tell(p.chat_id, INFO_TEXT)
        else:
            tell(p.chat_id, FROWNING_FACE + " Sorry, I don't understand what you have input")

# ================================
# GO TO STATE 1: GAME SYNONIM
# ================================


def goToState1(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    if giveInstruction:
        exerciseId, sentence, wordIndexToReplace, wordsToReplace, falseSynonymes, trueSynonymes = exercise_synonim.getRandomExercise()
        sentenceWithBoldWord = getSentenceWithBoldedWord(sentence, wordIndexToReplace, wordsToReplace)
        plural = 's' if len(wordsToReplace.split()) > 1 else ''
        instructions = utility.unindent(
            """
            I've chosen the following sentence for you:\n
            {0}\n
            Select an option from the following list which is a synonym of the word{1} in bold text ({2}).
            """.format(sentenceWithBoldWord, plural, wordsToReplace)
        )
        options = falseSynonymes + trueSynonymes
        random.shuffle(options)
        options_text = [BULLET_POINT + ' /' + str(n) + ': ' + x for n, x in enumerate(options, 1)]
        instructions += '\n'.join(options_text)
        number_buttons = [str(x) for x in range(1,len(options)+1)]
        kb = utility.distributeElementMaxSize(number_buttons)
        kb.append([BUTTON_EXIT])
        tell(p.chat_id, instructions, kb, one_time_keyboard=False)
        p.setLastExerciseNumberAndOptions(exerciseId, options)
    else:
        if input == '':
            tell(p.chat_id, "Not a valid input.")
        elif input == BUTTON_EXIT:
            restart(p)
        #elif input == BUTTON_NEXT_SENTENCE:
        #    repeatState(p)
        else:
            exerciseId, exerciseOptions = p.getLastExerciseIdAndOptions()
            exerciseId, sentence, wordIndexToReplace, wordsToReplace, falseSynonymes, trueSynonymes = exercise_synonim.getExercizeId(exerciseId)
            if input.startswith('/'):
                input = input[1:]
            if utility.representsIntBetween(input, 1, len(exerciseOptions)+1):
                number = int(input)
                chosenWord = exerciseOptions[number - 1]
            else:
                #tell(p.chat_id, FROWNING_FACE + " Sorry, I don't understand what you have input")
                chosenWord = input
            msg = "You have chosen *{0}*.\n".format(chosenWord)
            sendWaitingAction(p.chat_id, sleep_time=0.5)
            if chosenWord in trueSynonymes:
                msg += "😄 Great, your answer is correct!"
                #kb = [[BUTTON_NEXT_SENTENCE], [BUTTON_EXIT]]
                kb = [[BUTTON_EXIT]]
                tell(p.chat_id, msg, kb)
                sendWaitingAction(p.chat_id, sleep_time=1)
                repeatState(p)
            else:
                msg += "🙁 I'm sorry, your answer is NOT correct, try again"
                tell(p.chat_id, msg)

def getSentenceWithBoldedWord(sentence, wordIndexToReplace, wordsToReplace):
    words = sentence.split()
    logging.debug("Split words: " + str(words))
    numberOfWordsToReplace = len(wordsToReplace.split())
    for i in range(wordIndexToReplace, wordIndexToReplace+numberOfWordsToReplace):
        words[i] = '*' + words[i] + '*'
    logging.debug("Chosend index: {0}. Word: {1} ".format(str(wordIndexToReplace), words[wordIndexToReplace]))
    return ' '.join(words)

# ================================
# GO TO STATE 2: GAME SYNONIM
# ================================

def goToState2(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    if giveInstruction:
        intruder_index, options = exercise_intruder.getRandomExercise()
        instructions = "Which word does not belong here? " \
                       "Click on the intruder or on *{}* if you think there is no intruder.\n".format(BUTTON_NO_INTRUDER)
        options_text = [BULLET_POINT + ' /' + str(n) + ': ' + x for n, x in enumerate(options, 1)]
        instructions += '\n'.join(options_text)
        number_buttons = [str(x) for x in range(1,len(options)+1)]
        kb = utility.distributeElementMaxSize(number_buttons)
        kb.append([BUTTON_NO_INTRUDER])
        kb.append([BUTTON_EXIT])
        tell(p.chat_id, instructions, kb, one_time_keyboard=False)
        p.setLastExerciseNumberAndOptions(intruder_index, options)
    else:
        if input == '':
            tell(p.chat_id, "Not a valid input.")
        elif input == BUTTON_EXIT:
            restart(p)
        #elif input == BUTTON_NEXT_SENTENCE:
        #    repeatState(p)
        else:
            intruder_index, exerciseOptions = p.getLastExerciseIdAndOptions()
            if input.startswith('/'):
                input = input[1:]
            if utility.representsIntBetween(input, 1, len(exerciseOptions)+1):
                number = int(input)
                chosenWord = exerciseOptions[number - 1]
            else:
                #tell(p.chat_id, FROWNING_FACE + " Sorry, I don't understand what you have input")
                chosenWord = input
            msg = "You have chosen *{0}*.\n".format(chosenWord)
            sendWaitingAction(p.chat_id, sleep_time=0.5)
            chosen_index =  exerciseOptions.index(chosenWord) if chosenWord in exerciseOptions else -1
            if (chosenWord==BUTTON_NO_INTRUDER and intruder_index==-1) or chosen_index == intruder_index:
                msg += "😄 Great, your answer is correct!"
                #kb = [[BUTTON_NEXT_SENTENCE], [BUTTON_EXIT]]
                kb = [[BUTTON_EXIT]]
                tell(p.chat_id, msg, kb)
                sendWaitingAction(p.chat_id, sleep_time=1)
                repeatState(p)
            else:
                msg += "🙁 I'm sorry, your answer is NOT correct, try again"
                tell(p.chat_id, msg)

# ================================
# ================================
# ================================


class MeHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        self.response.write(json.dumps(json.load(urllib2.urlopen(key.BASE_URL + 'getMe'))))


class SetWebhookHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        url = self.request.get('url')
        if url:
            self.response.write(
                json.dumps(json.load(urllib2.urlopen(key.BASE_URL + 'setWebhook', urllib.urlencode({'url': url})))))



# ================================
# ================================
# ================================


class WebhookHandler(webapp2.RequestHandler):
    def post(self):
        urlfetch.set_default_fetch_deadline(60)
        body = json.loads(self.request.body)
        logging.info('request body:')
        logging.info(body)
        self.response.write(json.dumps(body))

        # update_id = body['update_id']
        if 'message' not in body:
            return
        message = body['message']
        # message_id = message.get('message_id')
        # date = message.get('date')
        if "chat" not in message:
            return
        # fr = message.get('from')
        chat = message['chat']
        chat_id = chat['id']
        if "first_name" not in chat:
            return
        text = message.get('text').encode('utf-8') if "text" in message else ''
        name = chat["first_name"].encode('utf-8')
        last_name = chat["last_name"].encode('utf-8') if "last_name" in chat else None
        username = chat["username"] if "username" in chat else None
        location = message["location"] if "location" in message else None
        contact = message["contact"] if "contact" in message else None

        # u'contact': {u'phone_number': u'393496521697', u'first_name': u'Federico', u'last_name': u'Sangati',
        #             u'user_id': 130870321}
        # logging.debug('location: ' + str(location))

        def reply(msg=None, kb=None, markdown=False, inlineKeyboardMarkup=False):
            tell(chat_id, msg, kb, markdown, inlineKeyboardMarkup)

        p = person.getPersonByChatId(chat_id)

        if p is None:
            # new user
            logging.info("Text: " + text)
            if text == '/help':
                reply(ISTRUZIONI)
            elif text.startswith("/start"):
                tell_masters("New user: " + name)
                p = person.addPerson(chat_id, name, last_name, username)
                reply("Ciao {0}, welcome in LingoGameBot!".format(name))
                restart(p)
            else:
                reply("Press on /start if you want to begin. "
                      "If you encounter any problem, please contact @kercos")
        else:
            # known user
            p.updateUsername(username)
            if text == '/state':
                if p.state in STATES:
                    reply("You are in state " + str(p.state) + ": " + STATES[p.state])
                else:
                    reply("You are in state " + str(p.state))
            elif text.startswith("/start"):
                reply("Hi {0}, welcome back in LingoGameBot!".format(name))
                p.setEnabled(True, put=False)
                restart(p)
            elif WORK_IN_PROGRESS and p.chat_id != key.FEDE_CHAT_ID:
                reply(UNDER_CONSTRUCTION + " The system is under maintanance, try again later.")
            else:
                logging.debug("Sending {0} to state {1}. Input: '{2}'".format(p.getName(), str(p.state), text))
                repeatState(p, input=text, contact=contact)

    def handle_exception(self, exception, debug_mode):
        logging.exception(exception)
        tell(key.FEDE_CHAT_ID, "❗ Detected Exception: " + str(exception), markdown=False)

def report_exception():
    import traceback
    msg = "❗ Detected Exception: " + traceback.format_exc()
    tell(key.FEDE_CHAT_ID, msg, markdown=False)
    logging.error(msg)


app = webapp2.WSGIApplication([
    ('/me', MeHandler),
    #    ('/_ah/channel/connected/', DashboardConnectedHandler),
    #    ('/_ah/channel/disconnected/', DashboardDisconnectedHandler),
    ('/set_webhook', SetWebhookHandler),
    ('/webhook', WebhookHandler),
], debug=True)

possibles = globals().copy()
possibles.update(locals())
