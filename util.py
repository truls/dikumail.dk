import fcntl
import hashlib
import time
import os
import sys
from contextlib import contextmanager
import re

import smtplib
from email.mime.text import MIMEText

sys.path.append("/var/lib/mailman")
from Mailman import mm_cfg
from Mailman import MailList
from Mailman import Utils
from Mailman import Message
from Mailman import Errors

def send_email(to, message, subject):
    fr = 'mailman-owner@dikumail.dk'

    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['To'] = to
    msg['From'] = fr

    s = smtplib.SMTP('localhost')
    s.sendmail(fr, to, msg.as_string())
    s.quit()

class Cookies(object):
    def __init__(self, cstr):
        self.cookies = {}
        for c in cstr.split(';'):
            k, v = c.split('=')
            self.cookies[k] = v

    def __getitem__(self, k):
        return self.cookies[k]
    def __setitem__(self, k, v):
        return self.cookies[k]

class _FormField(object):
    """
    The purpose of this class is to wrap a string value guarded by a
    validator regexp and hold a human readable reason for field
    inavlidity

    When Value is set to a string that matches the validator
    regexp. The error message is cleared and state switches to valid

    When value is set to a string that doesn't match the validator
    regexp, the error message is set to default_error, value is
    cleared and the state switches to invalid

    When error is modified, the value is cleared and the state
    switches to invalid
    """

    def __init__(self, validator, default_value, default_error):
        self.validator = re.compile(validator)
        self.default_error = default_error
        self.default_value = default_value
        self.val = default_value
        self.error_msg = None
        self.valid_state = False

    @property
    def value(self):
        return self.val
    @value.setter
    def value(self, v):
        v = str(v)
        if self.validator.match(v):
            self.val = v
            self.error_msg = None
            self.valid_state = True
            return
        self.val = self.default_value
        self.error_msg = self.default_error
        self.valid_state = False

    @property
    def error(self):
        return self.error_msg
    @error.setter
    def error(self, v):
        self.error_msg = v
        self.valid_state = False

    @property
    def valid(self):
        return self.valid_state

    def __str__(self):
        return self.value
    def __unicode__(self):
        return self.value

class FormData(object):
    def __init__(self, fdict):
        self.form = {}
        for k, v in fdict.iteritems():
            self.form[k] = _FormField(v[0], v[1], v[2])

    @property
    def valid(self):
        for f in self.form.itervalues():
            if not f.valid:
                return False
        return True

    def readform(self, cgiform):
        """
        Clones a form produced by the python cgi module
        """
        for k in self.form.iterkeys():
            if k in cgiform:
                self.form[k].value = str(cgiform[k].value)
            else:
                self.form[k].value = ''

    def __getitem__(self, key):
        return self.form[key]

class ListAlreadyExists(Exception):
    pass

class MMList(object):

    def __init__(self, lst, domain):
        self.list = lst.lower()
        self.domain = domain.lower()
        try:
            self.mlist = MailList.MailList(self.name, lock=0)
        except Errors.MMUnknownListError:
            #FIXME: Is it really wise to simply create an empty listinstance here?
            self.mlist = MailList.MailList()

    @property
    def name(self):
        if self.domain == '':
            return self.list
        return "%s--%s" % (self.domain, self.list)

    @property
    def exists(self):
        return Utils.list_exists(self.name)

    @contextmanager
    def lock(self):
        try:
            self.mlist.Lock()
            yield self.mlist
            self.mlist.Save()
            self.mlist.Unlock()
        finally:
            self.mlist.Unlock()

    @property
    def owners(self):
        return self.mlist.owner

    @staticmethod
    def from_email(email):
        try:
            name, domain = form['listaddr'].value.split('@')
        except ValueError:
            name, domain = (form['listaddr'].value, '')

        return MMList(name, domain)

    def add_alias(self, name):
        with self.lock():
            aliases = self.mlist.acceptable_aliases.split('\n')
            aliases.append(name)
            self.mlist.acceptable_aliases = '\n'.join(aliases)

    def auth(self, contexts, password):
        return self.mlist.Authenticate(contexts, password, None)

    def auth_admin(self, email, password):
        authcontexts = (mm_cfg.AuthListAdmin, mm_cfg.AuthSiteAdmin)
        siteowners = MMList(mm_cfg.MAILMAN_SITE_LIST, '').owners

        # Check that email is a list administrator and is logging in with a list admin password
        return (email in self.mlist.owner or email in siteowners) and \
          self.mlist.Authenticate(authcontexts, password) in authcontexts

    def create(self, email):
        if self.exists:
            raise ListAlreadyExists

        langs = [mm_cfg.DEFAULT_SERVER_LANGUAGE]
        pw = Utils.MakeRandomPassword()
        pw_hashed = Utils.sha_new(pw).hexdigest()
        urlhost = mm_cfg.DEFAULT_URL_HOST
        host_name = mm_cfg.DEFAULT_EMAIL_HOST
        web_page_url = mm_cfg.DEFAULT_URL_PATTERN % urlhost

        # TODO: Add some atomicity. We should roll back changes using
        #       a try/else if something (like MTA alias update) fails
        #       before the function terminates.

        try:
            oldmask = os.umask(002)
            self.mlist.Create(self.name, email, pw_hashed, langs=langs,
                              emailhost=host_name, urlhost=urlhost)
            self.mlist.preferred_language = langs[0]

            # Reply-To set to list address
            self.mlist.reply_goes_to_list = 2
            self.mlist.reply_to_address = "%s@%s" % (self.list, self.domain)

            # Allow messages from listname@domain
            self.mlist.acceptable_aliases = "%s@%s\n" % (self.list, self.domain)

            self.mlist.subject_prefix = "[%s] " % (self.list)
            self.mlist.msg_footer = ""
            self.mlist.subscribe_policy = 2 # Confirm and approve
            self.mlist.max_message_size = 20480 # 20M

            self.mlist.Save()

        finally:
            os.umask(oldmask)
            self.mlist.Unlock()

        if mm_cfg.MTA:
            modname = 'Mailman.MTA.' + mm_cfg.MTA
            __import__(modname)
            sys.modules[modname].create(self.mlist)

        siteowner = Utils.get_site_email(self.mlist.host_name, 'owner')
        text = Utils.maketext(
            'newlist.txt',
            {'listname'    : self.name,
             'password'    : pw,
             'admin_url'   : self.mlist.GetScriptURL('admin', absolute=1),
             'listinfo_url': self.mlist.GetScriptURL('listinfo', absolute=1),
             'requestaddr' : self.mlist.GetRequestEmail(),
             'siteowner'   : siteowner,
             }, mlist=self.mlist)


        msg = Message.UserNotification(email, siteowner, 'Your new mailing list: %s' % self.name,
                                        text, self.mlist.preferred_language)
        msg.send(self.mlist)


class NoSuchTokenError(Exception):
    pass
class TokenExpiredError(Exception):
    pass

class TokenHandler(object):
    def __init__(self, tokendb, validity = 3600):
        self.tokendb = tokendb
        self.validity = validity

        #FIXME: Create tokenfile if missing and check permissions

    def new(self, params = None):
        with open(self.tokendb, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            token = self._rndhash()
            now = time.time() + self.validity
            f.write("%s %s %s\n" % (token, str(now), str(params)))
            return token

    def get(self, pred):
        if not callable(pred):
            raise TypeError

        for token, when, data in self._token_it():
            if pred(token, when, data):
                if self._expired(when):
                    raise TokenExpiredError
                return (token, when, data)
        raise NoSuchTokenError

    def get_by_token(self, token):
        t, w, data = self.get(lambda t, a, b: t == token)
        return data

    def delete(self, pred):
        keep = []
        for token, when, data in self._token_it():
            if self._expired(when) or pred(token, when, data):
                continue
            keep.append((token, when, data))
        with open(self.tokendb, 'w+') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            for token, when, data in keep:
                f.write(' '.join((token, str(when), data)))

    def delete_token(self, token):
        self.delete(lambda t, a, b: t == token)

    def cleanup(self, token):
        self.delete(lambda a, b, c: True)

    def _rndhash(self):
        with open("/dev/urandom", 'r+') as f:
            h = hashlib.sha1()
            h.update(f.read(20))
            return h.hexdigest()

    def _token_it(self):
        with open(self.tokendb, 'r+') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            for t in f:
                a, b, c = tuple(t.split(' ', 2))
                yield (a, float(b), c)

    def _expired(self, when):
        return time.time() > when
