#!/usr/bin/python2.7

import cgi
import cgitb
cgitb.enable()
from util import *
import os
import sys
import re

from jinja2 import Environment, FileSystemLoader
jjenv = Environment(loader=FileSystemLoader(os.path.join(os.path.realpath(os.path.split(__file__)[0]), "templates")))

tokenlist = "/var/cache/token_cache"

def send_tokenmail(to, name, token):

    message = """
Here is the link for finalizing the creation of your mailing list %s

http://www.dikumail.dk/create-list.py?confirm=%s

Enjoy your list!

- dikulist.dk
"""
    send_email(to, message % (name, token), "Confirm your mailing list")

def main():
    print 'Content-Type: text/html; charset=utf-8'
    print ''

    formdef = {'listname': ('^[a-zA-Z][a-zA-Z0-9-]{2,}$', '', 'Invalid listname'),
               'email': ('^[a-zA-Z][a-zA-Z0-9-_@+.]{2,}$', '', 'Invalid email'),
                'domaintype': ('^[0-9]+$', "0", ''),
                'domainname': ('^[a-zA-Z0-9-.]{4,}$', '', 'Invalid domainname'),
                 'turing': ('^.*[jJ][yY][rR][kK][iI].*$', '', 'Wrong answer')}
    #domaintypefield = FormField('domaintype' guard='regex')
    #domainfield = FormField('domainname', guard='regex',
    #                        valid_if = lambda: domaintypefield.value == '0',
    #                        valid_if = lambda x: x['domaintype'].value == '0'
    formdata = FormData(formdef)
    
    # Decide handler
    ferror = {}    
    form = cgi.FieldStorage()

    
    if "listrequest" in form:

        tmgr = TokenHandler(tokenlist)

        #for f in formdef.iterkeys():
        #    if f in form:
        #        formdata[f].value = str(form[f].value)
        #    else:
        #        formdata[f].value = ''
        formdata.readform(form)

        if formdata["domaintype"].value == "0":
            formdata["domainname"].value = 'dikumail.dk'

        if MMList(formdata["listname"].value,
                  formdata["domainname"]).exists:
            formdata["listname"].error = "List already exists"
        else:
            try:
                if tmgr.get(lambda a, b, data: ' '.join((formdata["listname"].value,
                                                         formdata['domainname'].value))
                                                   in data):
                    formdata["listname"].error = "Somebody already requested a list by that name. Wait an hour to see if they let their request expire or choose a different name"
            except NoSuchTokenError:
                pass
            except TokenExpiredError:
                pass
           
        if formdata.valid:
            tmpl = jjenv.get_template('createstatus.html')
            
            # Grab a token
            token = tmgr.new("%s %s %s" % (formdata['listname'].value, formdata['domainname']
                                           , formdata["email"].value))

            send_tokenmail(form["email"].value,
                           MMList(form['listname'].value,
                                  formdata['domainname']).name, token)
            
            print tmpl.render(state="sent", form=formdata)
            return

    elif "confirm" in form:
        tmgr = TokenHandler(tokenlist)
        tmpl = jjenv.get_template("createstatus.html")
        token = form["confirm"].value

        try:
            listname, domain, email = tmgr.get_by_token(token).split()
        except NoSuchTokenError:
            print tmpl.render(state="notoken")
            return

        try:
            mmlist = MMList(listname, domain)
            mmlist.create(email)
            tmgr.delete_token(token)
        except ListAlreadyExists:
            print tmpl.render(state="exists")
            return

        print tmpl.render(state="success")
        return
    
    tmpl = jjenv.get_template('createlist.html')
    print tmpl.render(form=formdata)

if __name__ == "__main__":
    main()
    


