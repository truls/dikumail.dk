#!/usr/bin/python2.7

import cgi
import cgitb
cgitb.enable()

from util import *
import auth
from jinja2 import Environment, FileSystemLoader
jjenv = Environment(loader=FileSystemLoader(os.path.join(os.path.realpath(os.path.split(__file__)[0]), "templates")))



