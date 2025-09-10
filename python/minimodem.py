#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os,sys,re
import subprocess
import argparse
import alsaaudio
from time import strftime,localtime,sleep,time

########################################################################
# config
########################################################################
mode = 0    # 0: menu, 1: command line (-h for help)
tx_dir = '/home/pi/Minimodem/send/'
rx_dir = '/home/pi/Minimodem/receive/'
alsa_tx_conf = '-A1'    # ALSA: tag -Ax where x is the card index in 'aplay -l', PulseAudio: empty
alsa_rx_conf = '-A1'    # ALSA: tag -Ax where x is the card index in 'arecord -l', PulseAudio: empty
alsa_cardindex = 1      # alsaaudio card index
alsa_play = 'PCM'   # alsaaudio playback mixer object name, can be found with 'alsaaudio.mixers(cardindex)'
alsa_rec = 'Mic'     # alsaaudio record mixer object name, can be found with 'alsaaudio.mixers(cardindex)'
alsa_play_vol = 40       # range 0-100, verify audio levels with 'alsamixer'
alsa_rec_vol = 85        # range 0-100, verify audio levels with 'alsamixer'
baudrate = 1200          # baudrate = symbols/sec
msg_start_str = '- VOX DELAY -'     # message header for VOX delay
msg_start_count = 15        # message header count
msg_stop_str = '- END -'    # message footer
msg_call_str = '- CALLSIGN: '       # callsign line added in message
msg_rcv_str = '- TO: '              # receiver line added in message
msg_time_str = '- TIMESTAMP: '      # timestamp line added in message
call_sign = 'Mickey123'      # callsign when transmitting, use only alphanumeric characters

########################################################################

# author: SCA
# email: chconsultinghk[at]gmail.com
# python 2.7
# changelog
# v1: initial version
# v2: add audio level config
# v3: add start/stop strings automatically in mode 'send text file', add callsign+timestamp in text message
# v4: add receiver callsign in message header


# https://pymotw.com/2/argparse/
# https://www.golinuxcloud.com/python-argparse/
# https://larsimmisch.github.io/pyalsaaudio/libalsaaudio.html
# https://www.azavea.com/blog/2014/03/24/solving-unicode-problems-in-python-2-7/
# https://janakiev.com/blog/python-shell-commands/
# https://www.programmersought.com/article/858168763/
# https://stackoverflow.com/questions/18739239/python-how-to-get-stdout-after-running-os-system
# os.system() does wait for its process to complete before returning
# os.system() send minimodem tx command: warning message 'ALSA lib pcm.c:(snd_pcm_recover) underrun occurred'
# os.system() just runs the process but doesn't capture the output
# https://superuser.com/questions/262942/whats-different-between-ctrlz-and-ctrlc-in-unix-command-line
# CTRL+Z is used for suspending a process by sending it the signal SIGSTOP, which cannot be intercepted by the program.
# While CTRL+C is used to kill a process with the signal SIGINT, and can be intercepted by a program so it can clean its self up 
# before exiting, or not exit at all.
# Always press CTRL+C to exit minimodem
# if you exit by pressing CTRL+Z, when you relaunch the script: error 'Cannot create ALSA stream: Device or resource busy'


def cmd(): 
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('-t', action='store', dest='file', help='transmit text file')
        parser.add_argument('-c', action='store', dest='callsign', help='add receiver callsign for transmission')
        parser.add_argument('-r', action="store", dest='timeout', type=int, help='receive text files until timeout expired (sec)')
        parser.add_argument('-s', action='store_true', dest='level', default=False, help='set audio levels')
        results = parser.parse_args()
        if results.callsign:    # input receiver callsign
            rcv_sign = results.callsign
        else:
            rcv_sign = ''
        if results.file:    # transmit text file
            txt_path = os.path.join(tx_dir,results.file)
            if os.path.isfile(txt_path):
                #cmd = 'cat %s | minimodem --tx %d %s' %(txt_path,baudrate,alsa_tx_conf)
                with open(txt_path, 'r') as tf:
                    msg_str = tf.read()
                timestamp = strftime('20%y%m%d_%H%M%S',localtime())
                tx_str = (msg_start_str+'\n')*msg_start_count+msg_call_str+call_sign+'\n'+msg_rcv_str+rcv_sign+'\n'+msg_time_str+timestamp+'\n'+msg_str+'\n'+msg_stop_str
                cmd = 'echo "%s" | minimodem --tx %d %s' %(tx_str,baudrate,alsa_tx_conf)
                #print 'command: ' + cmd
                print 'attention: to exit press CTRL+C, do not press CTRL+Z'
                os.system(cmd)
                print timestamp+': '+'message sent'
            else:
                print 'cannot find text file in %s!' %(tx_dir)
        elif results.timeout:     # receive text files, timeout does not work well
            timeout = time() + results.timeout
            #print timeout
            while time() < timeout:
                cmd = 'minimodem --rx-one --quiet %d %s' %(baudrate,alsa_rx_conf)
                #print 'command: ' + cmd
                #print time()
                print 'attention: to exit press CTRL+C, do not press CTRL+Z'
                data = ''
                while time() < timeout:
                    data = subprocess.check_output(cmd, shell=True)
                    #print data
                    if re.search(msg_start_str,data):
                        break # exit the loop
                if time() < timeout:
                    try:
                        rx_callsign = re.search(r'(%s)(\w+)(\s)' % msg_call_str,data).group(2)
                    except AttributeError:
                        rx_callsign = ''
                    try:
                        rx_receiver = re.search(r'(%s)(\w+)(\s)' % msg_rcv_str,data).group(2)
                    except AttributeError:
                        rx_receiver = ''
                    timestamp = strftime('20%y%m%d_%H%M%S',localtime())
                    txt_file = 'text_%s_%s_%s.txt' %(rx_callsign,rx_receiver,timestamp)
                    txt_path = os.path.join(rx_dir,txt_file)
                    print timestamp+': '+'message received and saved in ' + txt_path
                    with open(txt_path, 'w') as tf:
                        tf.write(data)
        elif results.level:     # set audio levels
            play  = alsaaudio.Mixer(alsa_play, cardindex=alsa_cardindex)
            play.setvolume(alsa_play_vol)
            pvol = play.getvolume(0)
            print 'playback volume: ',pvol
            rec  = alsaaudio.Mixer(alsa_rec, cardindex=alsa_cardindex)
            rec.setvolume(alsa_rec_vol)
            rvol = rec.getvolume(1)
            print 'record volume: ',rvol
        else:
            print 'error: wrong arguments (-h for help)'
    except Exception as e:
        print e

def menu():
    try:
        while True:
            print '----- Minimodem Interface For Packet Radio -----'
            disp_str = '1) send text\n2) send text file\n3) receive text\n4) receive text file\n5) set audio levels \n6) exit\nselection?\n'
            cat_no = int(raw_input(disp_str))
            if cat_no == 1: # send text in console
                rcv_sign = raw_input('receiver callsign?\n')
                msg_str = raw_input('message?\n')
                timestamp = strftime('20%y%m%d_%H%M%S',localtime())
                tx_str = (msg_start_str+'\n')*msg_start_count+msg_call_str+call_sign+'\n'+msg_rcv_str+rcv_sign+'\n'+msg_time_str+timestamp+'\n'+msg_str+'\n'+msg_stop_str
                cmd = 'echo "%s" | minimodem --tx %d %s' %(tx_str,baudrate,alsa_tx_conf)
                #print 'command: ' + cmd
                print 'attention: to exit press CTRL+C, do not press CTRL+Z'
                os.system(cmd)
                print timestamp+': '+'message sent'
            elif cat_no == 2: # send text file
                rcv_sign = raw_input('receiver callsign?\n')
                print 'content of %s:' %(tx_dir)
                for i in os.listdir(tx_dir):
                    print '* ' + i
                disp_str = 'text file name?\r\n'
                txt_file = raw_input(disp_str)
                txt_path = os.path.join(tx_dir,txt_file)
                if not os.path.isfile(txt_path):
                    print 'cannot find text file in %s!' %(tx_dir)
                    continue    # returns to the beginning of the loop
                else:
                    #cmd = 'cat %s | minimodem --tx %d %s' %(txt_path,baudrate,alsa_tx_conf)
                    with open(txt_path, 'r') as tf:
                        msg_str = tf.read()
                    timestamp = strftime('20%y%m%d_%H%M%S',localtime())
                    tx_str = (msg_start_str+'\n')*msg_start_count+msg_call_str+call_sign+'\n'+msg_rcv_str+rcv_sign+'\n'+msg_time_str+timestamp+'\n'+msg_str+'\n'+msg_stop_str
                    cmd = 'echo "%s" | minimodem --tx %d %s' %(tx_str,baudrate,alsa_tx_conf)
                    #print 'command: ' + cmd
                    print 'attention: to exit press CTRL+C, do not press CTRL+Z'
                    os.system(cmd)
                    print timestamp+': '+'text file sent'
            elif cat_no == 3: # receive text in console
                cmd = 'minimodem --rx --quiet %d %s' %(baudrate,alsa_rx_conf)
                #print 'command: ' + cmd
                print 'attention: to exit press CTRL+C, do not press CTRL+Z'
                os.system(cmd)
            elif cat_no == 4: # receive text file
                cmd = 'minimodem --rx-one --quiet %d %s' %(baudrate,alsa_rx_conf)
                #print 'command: ' + cmd
                print 'attention: to exit press CTRL+C, do not press CTRL+Z'
                data = ''
                while True:
                    data = subprocess.check_output(cmd, shell=True)
                    #print data
                    if re.search(msg_start_str,data):
                        break # exit the loop
                try:
                    rx_callsign = re.search(r'(%s)(\w+)(\s)' % msg_call_str,data).group(2)
                except AttributeError:
                    rx_callsign = ''
                try:
                    rx_receiver = re.search(r'(%s)(\w+)(\s)' % msg_rcv_str,data).group(2)
                except AttributeError:
                    rx_receiver = ''
                timestamp = strftime('20%y%m%d_%H%M%S',localtime())
                txt_file = 'text_%s_%s_%s.txt' %(rx_callsign,rx_receiver,timestamp)
                txt_path = os.path.join(rx_dir,txt_file)
                with open(txt_path, 'w') as tf:
                    tf.write(data)
                print timestamp+': '+'message received and saved in ' + txt_path
                #timestamp = strftime('20%y%m%d_%H%M%S',localtime())
                #txt_file = 'text_%s.txt' %(timestamp)
                #txt_path = os.path.join(rx_dir,txt_file)
                #cmd = 'minimodem --rx-one %d %s > %s' %(baudrate,alsa_rx_conf,txt_path)
                #print 'command: ' + cmd
                #print 'attention: to exit press CTRL+C, do not press CTRL+Z'
                #os.system(cmd)
            elif cat_no == 5:   # set audio levels
                #print alsaaudio.mixers(alsa_cardindex)
                play  = alsaaudio.Mixer(alsa_play, cardindex=alsa_cardindex)
                #print play.volumecap()
                play.setvolume(alsa_play_vol)
                pvol = play.getvolume(0)
                print 'playback volume: ',pvol
                rec  = alsaaudio.Mixer(alsa_rec, cardindex=alsa_cardindex)
                #print rec.volumecap()
                rec.setvolume(alsa_rec_vol)
                rvol = rec.getvolume(1)
                print 'record volume: ',rvol
            elif cat_no == 6:   # exit
                break # exit the loop
            else:
                continue    # returns to the beginning of the loop
            #raw_input('press any key')
    except Exception as e:
        print e

if __name__ == '__main__':
    if mode == 0:
        menu()
    else:
        cmd()
