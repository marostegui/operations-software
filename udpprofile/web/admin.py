#!/usr/bin/python

import cgi
import cgitb
import config
import datetime
import shelve
import sys

cgitb.enable()

password=config.password

print "Content-type: text/html\n"

form=cgi.SvFormContentDict()

if 'password' in form:
    if form['password'] != "" and form['password'] != password:
        print "access denied!!!!!!!!!1111oneoneeleven"
        sys.exit()
    else:
        authed=True
else:
    authed=False

print """
    <script>function deletesample(sample) {form=document.forms['actions'];form['sample'].value=sample;form.submit();}</script>
    <form name='actions' method='POST' action='admin.py'>
    <input type='submit' name='action' value='take'>
    <input type='submit' name='action' value='clear'>
    <input type='hidden' name='sample' value=''>
    <input type='%s' name='password' value='%s'
    </form>""" % ((authed and 'hidden' or 'password'),(authed and password or ''))

store = shelve.open('baselines')

if 'action' not in form:
    if 'sample' in form and authed:
        del store[form['sample']]
elif form['action'] == 'clear' and authed:
    import socket
    sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    sock.sendto('-truncate',(config.host,config.port))
elif form['action'] == 'take' and authed:
    from extractprofile import SocketProfile
    store[str(datetime.datetime.now()).replace(" ","-")] = SocketProfile(config.host,config.port).extract()
elif 'sample' in form and authed:
    del store[form['sample']]

for entry in store.keys():
    print """<div><a href='report.py?sample=%s'>%s</a> <a href='javascript:deletesample("%s")'>delete</a></div>""" % (entry,entry,entry)

print "<div><a href='report.py'>current</a></div>"
