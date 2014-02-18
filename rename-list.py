#!/usr/bin/python2.7

import cgi
import cgitb
cgitb.enable()

import os

from util import *
import auth
from jinja2 import Environment, FileSystemLoader
jjenv = Environment(loader=FileSystemLoader(os.path.join(os.path.realpath(os.path.split(__file__)[0]), "templates")))

import auth

@auth.authorize
def main():
    print str(HttpHeaders())
    print "foobar"
    print "Is authorized to modify the list " + auth.context.listname

if __name__ == "__main__":
    main()


    
