#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

import cgi
import cgitb
cgitb.enable()

import os

from util import *

from jinja2 import Environment, FileSystemLoader
jjenv = Environment(loader=FileSystemLoader(os.path.join(os.path.realpath(os.path.split(__file__)[0]), "templates")))

tokenlist = "/var/cache/token_cache"

class Context(object):
    def __init__(self):
        self.authed = False
        self.listname = None

    @property
    def authed(self):
        return self.authed
    @authed.setter
    def authed(self, v):
        if not v is False or not v is True:
            raise TypeError("Can only be set to a boolean value")
        self.authed = v

    @property
    def listname(self):
        if self.listname is None:
            raise NotAuthenticatedError
        return self.listname
    @authed.setter
    def listname(self, v):
        if not isinstance(v, bool):
            raise TypeError("Can only be set to a string")
        self.listname = v
context = Context()

class NotAuthenticatedError(Exception):
    pass

def is_authed():
    """
    TODO:
    Find a nice way to refresh the auth token upon validation so
    it doesn't just expire after one hour
    """

    tmgr = TokenHandler(tokenlist)

    try:
        token = Cookies(os.environ['HTTP_COOKIE'])['authkey']
    except KeyError:
        token = ''

    try:
        t, w, d = tmgr.get(lambda token, when, data: token == token and "auth" in data)
        # TODO: Auth token should be renewed here
        context.authed = True
        context.listname = d.split(' ')[1]
        return True
    except Exception as e:
        if not (isinstance(e, NoSuchTokenError) or
                isinstance(e, TokenExpiredError)):
            raise e
        #print 'Content-Type: text/html'
        #print ''
        #tmpl = jjenv.get_template("auth.html")
        #print tmpl.render(redir=os.environ['REQUEST_URI'], form=form)
        #print "Status: 303 See Other"
        #print 'Location: /auth.py?redir=' + os.environ['REQUEST_URI']
        #print ''
        show_form()
        return False
        
def authorize(f):
    # Decorator for preventing function execution unless user is authenticated
    def wrapper(*args, **kwargs):
        if is_authed():
            f(*args, **kwargs)
    return wrapper
    
def show_form():

    formdef = {'listaddr': ('^[a-zA-Z][a-zA-Z0-9-_@+.]{2,}$', '', 'Invalid address'),
               'email': ('^[a-zA-Z][a-zA-Z0-9-_@+.]{2,}$', '', 'Invalid email'),
               'password': ('.*', '', 'Invalid password')}
    form = FormData(formdef)

    cgiform = cgi.FieldStorage()
    #print cgiform
    
    tmgr = TokenHandler(tokenlist)
    
    # FIXME: Don't use input from browser here
    if not "redir" in cgiform:
        redir = tmgr.new(os.environ['REQUEST_URI'])
    else:
        redir = cgiform['redir'].value


    if "auth" in cgiform:
        form.readform(cgiform)
        
        mmlist = None
        # If from is completely filled out, check that list exists
        if form.valid:
            try:
                name, domain = form['listaddr'].value.split('@')
            except ValueError:
                name, domain = (form['listaddr'].value, '')
            
            mmlist = MMList(name, domain)
            if not mmlist.exists:
                form['listaddr'].error = "No such list"

        # If list exists, check credentials
        if form.valid:
            if not mmlist.auth_admin(form['email'].value, form['password'].value):
                form['password'].error = "Incorrect password or email is not list admin"

        # If credentails are ok, set authcookie and authenticate
        if form.valid:
            # Everything is ok. Authenticate!
            token = tmgr.new(params = "auth " + mmlist.name)
                
            # Write headers for redirection
            print str(HttpHeaders({'Status': "303 See Other",
                                   'Set-Cookie': 'authkey=' + token,
                                   'Location': tmgr.get_by_token(redir)}))
            return
    
    print str(HttpHeaders())
        
    tmpl = jjenv.get_template('auth.html')
    print tmpl.render(redir=redir, form=form)
        
def main():
    show_form()
    
if __name__ == "__main__":
    main()
    
