#!/usr/bin/python2.7

import cgi
import cgitb
cgitb.enable()

from util import *
import auth
from jinja2 import Environment, FileSystemLoader
jjenv = Environment(loader=FileSystemLoader(os.path.join(os.path.realpath(os.path.split(__file__)[0]), "templates")))

tokenlist = "/var/cache/token_cache"

def main():
    tmgr = TokenHandler(tokenlist)

    try:
        token = Cookies(os.environ['HTTP_COOKIE'])['authkey']
        tmgr.delete_token(token)
    except KeyError:
        pass
    except NoSuchTokenError:
        pass
    print str(HttpHeaders(HttpHeaders.defaults()),
              {'Set-Cookie': 'authkey=invalid'})
    tmpl = jjenv.get_template('logout.html')
    print tmpl.render()

if __name__ == "__main__":
    main()

