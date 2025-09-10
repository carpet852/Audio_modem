#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import re
import cgi

# Allow the python script to write files in tx_dir:
# $ chmod 777 send/
tx_dir = '/home/pi/Minimodem/send/'
rx_dir = '/home/pi/Minimodem/receive/'

form = cgi.FieldStorage() # parse form data

try:
    print('Content-type: text/html\n')
    print('<hr><a href=/>Back to main page</a><hr>')
    if not 'filename' in form:
        print('<br>Error: no filename!</br>')
    else:
        name = cgi.escape(form['filename'].value)
        data = cgi.escape(form['message'].value)
        txt_file = '%s.txt' % name
        txt_path = os.path.join(tx_dir,txt_file)
        with open(txt_path, 'w') as tf:
            tf.write(data)
        print('<br>Text file saved!</br>')
except Exception as E:
    print(E)
