#!/usr/bin/python2.7

import cgi
import cgitb
cgitb.enable()

import os

from util import *

from jinja2 import Environment, FileSystemLoader
jjenv = Environment(loader=FileSystemLoader(os.path.join(os.path.realpath(os.path.split(__file__)[0]), "templates")))

tokenlist = "/var/cache/token_cache"

class NotAuthenticatedError(Exception):
    pass

def is_authed():
    """
    TODO:
    Find a nice way to refresh the auth token upon validation so
    it doesn't just expire after one hour
    """
    
    tmgr = TokenHandler(tokenlist)
    #cgiform = cgi.FieldStorage()

    try:
        token = Cookies(os.environ['HTTP_COOKIE'])['authkey']
    except KeyError:
        token = ''

    try:
        tmgr.get_by_token(token)
        # TODO: Auth token should be renewed here
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

    #if "redir" in cgiform:
    #    redir = cgiform['redir'].value
    #else:
    #    redir = '/admin.py'
    tmgr = TokenHandler(tokenlist)
    
    # FIXME: Don't use input from browser here
    redir = tmgr.new(os.environ['REQUEST_URI'])


    if "auth" in cgiform:
        form.readform(cgiform)
        
        #print 'Content-Type: text/html'
        #print 'Set-Cookie: authkey=foo;'
        #print 'Set-Cookie: authbar=bar;'
        #print ''
            
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
            token = tmgr.new(mmlist.name)
                
            # Write headers for redirection
            print 'Status: 303 See Other'
            print 'Set-Cookie: authkey=' + token
            print 'Location: ' + tmgr.get_by_token(redir)
            print ''
            return
        
    print 'Content-Type: text/html'
    print 'Cache-Control: no-cache'
    print 'Pragma: no-cache'
    print ''
        
    tmpl = jjenv.get_template('auth.html')
    print tmpl.render(redir=redir, form=form)
        
    #print os.environ

def main():
    pass
    
if __name__ == "__main__":
    main()
    
