#!/usr/bin/env python
# -*- coding: utf-8 -*-

# MPI3501 display, 480X320 dots resolution
# https://www.bogotobogo.com/python/python_subprocess_module.php
# https://www.pythonforbeginners.com/os/subprocess-for-system-administrators
# https://janakiev.com/blog/python-shell-commands/
# https://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
# https://github.com/PySimpleGUI/PySimpleGUI/issues/850
# https://github.com/PySimpleGUI/PySimpleGUI/issues/1243
# https://stackoverflow.com/questions/57643820/how-to-handle-gui-such-as-pysimplegui-from-going-into-not-responding-when-ru
# https://stackoverflow.com/questions/20078816/replace-non-ascii-characters-with-a-single-space
# https://www.simplilearn.com/tutorials/python-tutorial/global-variable-in-python
# https://forums.raspberrypi.com/viewtopic.php?t=233309
# https://larsimmisch.github.io/pyalsaaudio/libalsaaudio.html#alsaaudio.Mixer.setvolume
# https://larsimmisch.github.io/pyalsaaudio/libalsaaudio.html


import os,sys,re
import subprocess
import argparse
import alsaaudio
import signal
import Queue
import threading
from time import strftime,localtime,sleep,time
from subprocess import call
import PySimpleGUI27 as sg

########################################################################
# config
########################################################################
tx_dir = '/home/pi/Minimodem/send/'
rx_dir = '/home/pi/Minimodem/receive/'
alsa_tx_conf = '-A1'    # ALSA: tag -Ax where x is the card index in 'aplay -l', PulseAudio: empty
alsa_rx_conf = '-A1'    # ALSA: tag -Ax where x is the card index in 'arecord -l', PulseAudio: empty
alsa_cardindex = 1      # alsaaudio card index
# USB audio dict {'name': [alsa_play, alsa_rec, alsa_play_vol, alsa_rec_vol, alsa_rec_ch]}
# alsa_play: alsaaudio playback mixer object name, can be found with 'alsaaudio.mixers(cardindex)'
# alsa_rec: alsaaudio record mixer object name, can be found with 'alsaaudio.mixers(cardindex)'
# alsa_play_vol: range 0-100, verify audio levels with 'alsamixer'
# alsa_rec_vol: range 0-100, verify audio levels with 'alsamixer'
# alsa_rec_ch: number of Mic channels
alsa_card_dict = {  'UGWC': ['Speaker','Mic',20,85,1], 
                    'UGWOC': ['PCM','Mic',40,85,2]
                 }
alsa_card_default = 'UGWC'
baudrate = 1200          # baud=symbols/sec, 300 bauds more resistant to noise
msg_start_str = '- VOX DELAY -'     # message header for VOX delay
msg_start_count = 15        # message header count
msg_stop_str = '- END -'    # message footer
msg_call_str = '- CALLSIGN: '       # callsign line added in message
msg_rcv_str = '- TO: '        # receiver line added in message
msg_time_str = '- TIMESTAMP: '      # timestamp line added in message
call_sign = 'Mickey123'      # callsign when transmitting, use only alphanumeric characters
########################################################################

# author: SCA
# email: chconsultinghk[at]gmail.com
# python 2.7
# changelog
# v1: initial version with callsign+timestamp in message header
# v2: correct bugs, add RX single trig
# v3: add receiver callsign in message header, add filter by callsign
# v4: minor modifications
# v5: add USB audio interface config, modify set volume


def rx_data_thread(gui_queue, rx_dir, cmd, msg_start_str, msg_call_str, msg_rcv_str, call_sign, rx_save_file, rx_filter):
    # A worker thread that communicates with the GUI through a queue
    # This thread can block for as long as it wants and the GUI will not be affected
    # This thread will wait until rx_data is received and send it to the GUI

    # declare the global variables in all the functions where they are used
    global rx_on_flag
    global rx_flag
    global p2

    try:
        rx_data = ''
        #sg.Print('rx_on_flag:',rx_on_flag)
        #sg.Print('rx_flag:',rx_flag)
        while rx_on_flag:
            # (Linux) setsid creates a session and sets the process group ID if the calling process is not a process group leader
            p2 = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
            #sg.Print('RX process:',p2)
            rx_data, rx_err = p2.communicate() # returns when process is terminated
            rx_code = p2.returncode
            if re.search(msg_start_str,rx_data):
                break # exit the loop
        if rx_on_flag:
            timestamp = strftime('20%y%m%d_%H%M%S',localtime())
            print timestamp+': '+'message received'
            try:
                rx_callsign = re.search(r'(%s)(\w+)(\s)' % msg_call_str,rx_data).group(2)
            except AttributeError:
                rx_callsign = ''
            try:
                rx_receiver = re.search(r'(%s)(\w+)(\s)' % msg_rcv_str,rx_data).group(2)
            except AttributeError:
                rx_receiver = ''
            if rx_filter:
                if rx_receiver == call_sign:
                    if rx_save_file:
                        txt_file = 'text_%s_%s_%s.txt' %(rx_callsign,rx_receiver,timestamp)
                        txt_path = os.path.join(rx_dir,txt_file)
                        with open(txt_path, 'w') as tf:
                            tf.write(rx_data)
                        print timestamp+': '+'message saved in ' + txt_path
                else:
                    print timestamp+': '+'message discarded (wrong callsign)'
                    rx_data = ''
            else:
                if rx_save_file:
                    txt_file = 'text_%s_%s_%s.txt' %(rx_callsign,rx_receiver,timestamp)
                    txt_path = os.path.join(rx_dir,txt_file)
                    with open(txt_path, 'w') as tf:
                        tf.write(rx_data)
                    print timestamp+': '+'message saved in ' + txt_path
            gui_queue.put(rx_data)
            rx_flag = True
            #sg.Print(''.join(i for i in rx_data if ord(i)<128), rx_err, rx_code)    # sg.Print crash if non ascii characters
            #sg.Print('rx_on_flag:',rx_on_flag)
            #sg.Print('rx_flag:',rx_flag)

    except Exception as E:
        #sg.Print('rx_data_thread error: ',str(E))
        pass

def gui():
    
    # declare the global variables in all the functions where they are used
    global rx_on_flag
    global rx_flag
    global p2

    gui_queue = Queue.Queue()  # queue used to communicate between the gui and the threads
    
    try:
        txt_list = [i for i in os.listdir(tx_dir) if i.lower().endswith((".txt"))]
    except Exception as E:
        txt_list = []
        #sg.Print('txt list error:',E)
    
    alsa_play = alsa_card_dict[alsa_card_default][0]       # alsaaudio playback mixer object name, can be found with 'alsaaudio.mixers(cardindex)'
    alsa_rec = alsa_card_dict[alsa_card_default][1]        # alsaaudio record mixer object name, can be found with 'alsaaudio.mixers(cardindex)'
    alsa_play_vol = alsa_card_dict[alsa_card_default][2]   # range 0-100, verify audio levels with 'alsamixer'
    alsa_rec_vol = alsa_card_dict[alsa_card_default][3]    # range 0-100, verify audio levels with 'alsamixer'
    alsa_rec_ch = alsa_card_dict[alsa_card_default][4]     # number of Mic channels
    
    # FolderBrowse default target = same row, to the left
    conf_layout = [ [sg.Text('USB Audio Alsa Config'), sg.Combo(alsa_card_dict.keys(), default_value=alsa_card_default, size=(20, 1), enable_events=True, key='_usb_audio')],
                    [sg.Text('Alsa Playback Volume'), sg.InputText(default_text=alsa_play_vol,size=(3, 1),key='_alsa_play_vol'), 
                    sg.Text('Alsa Record Volume'), sg.InputText(default_text=alsa_rec_vol,size=(3, 1),key='_alsa_rec_vol')],
                    [sg.Button('Set Volume'), sg.Text('', size=(25, 1), key='_set_vol_msg')],
                    [sg.Text('TX directory'), sg.InputText(default_text=tx_dir,size=(25, 1),key='_tx_dir'), sg.FolderBrowse(key='_tx_dir_browse')],
                    [sg.Text('RX directory'), sg.InputText(default_text=rx_dir,size=(25, 1),key='_rx_dir'), sg.FolderBrowse(key='_rx_dir_browse')],
                    [sg.Text('Alsa TX config'), sg.InputText(default_text=alsa_tx_conf,size=(20, 1),key='_alsa_tx_conf')],
                    [sg.Text('Alsa RX config'), sg.InputText(default_text=alsa_rx_conf,size=(20, 1),key='_alsa_rx_conf')],
                    [sg.Text('Alsa Card Index'), sg.InputText(default_text=alsa_cardindex,size=(20, 1),key='_alsa_cardindex')],
                    [sg.Text('Alsa Playback Name'), sg.InputText(default_text=alsa_play,size=(20, 1),key='_alsa_play')],
                    [sg.Text('Alsa Record Name'), sg.InputText(default_text=alsa_rec,size=(20, 1),key='_alsa_rec')],
                    [sg.Text('Alsa Record Nb Channels'), sg.InputText(default_text=alsa_rec_ch,size=(20, 1),key='_alsa_rec_ch')],
                    [sg.Text('Baudrate'), sg.InputText(default_text=baudrate,size=(20, 1),key='_baudrate')],
                    [sg.Text('Message Start Header'), sg.InputText(default_text=msg_start_str,size=(20, 1),key='_msg_start_str')],
                    [sg.Text('Message Start Header Count'), sg.InputText(default_text=msg_start_count,size=(20, 1),key='_msg_start_count')],
                    [sg.Text('Message Stop Header'), sg.InputText(default_text=msg_stop_str,size=(20, 1),key='_msg_stop_str')],
                    [sg.Text('Message Timestamp Header'), sg.InputText(default_text=msg_time_str,size=(20, 1),key='_msg_time_str')],
                    [sg.Text('Message Callsign Header'), sg.InputText(default_text=msg_call_str,size=(20, 1),key='_msg_call_str')],
                    [sg.Text('Message Receiver Header'), sg.InputText(default_text=msg_rcv_str,size=(20, 1),key='_msg_rcv_str')],
                    [sg.Text('Callsign'), sg.InputText(default_text=call_sign,size=(30, 1),key='_call_sign')],
                    [sg.Checkbox('Filter messages received using Callsign', size=(40,1), default=False, key='_rx_filter')]]

    tx_layout = [   [sg.Text('Receiver Callsign', size=(20, 1)), sg.InputText(default_text='',key='_rcv_sign')],
                    [sg.Multiline(size=(55, 5), enter_submits=False, do_not_clear=True, default_text='type message here', key='_tx_input')],
                    [sg.Button('TX'), sg.Button('Stop TX'), sg.Button('Clear'),
                     sg.Listbox(values=sorted(txt_list), enable_events=True, size=(20,1), key='_txt_list'),],
                ]
              
    rx_layout = [   [sg.Multiline(size=(55, 6), enter_submits=False, do_not_clear=True, key='_rx_input')],
                    [sg.Button('RX'), sg.Button('Stop RX'),
                    sg.Checkbox('Save', size=(5,1), default=False, key='_rx_save_file'),
                    sg.Checkbox('Single Trig', size=(10,1), default=False, key='_rx_single_trig'),
                    sg.Text('RX OFF', size=(10, 1), key='_rx_msg'),]
                ]

    layout = [  [sg.TabGroup([[
                sg.Tab('Receive', rx_layout), 
                sg.Tab('Send', tx_layout), 
                sg.Tab('Config', [[sg.Column(conf_layout, size=(400,140), scrollable=True)]])]])],[sg.Output(size=(56, 3), key='_output')],
             ]

    # Create the Window
    window = sg.Window('Minimodem Interface', layout, return_keyboard_events=False, size=(460, 260))
    
    rx_on_flag = False
    rx_flag = False
    tx_flag = False

    # Event Loop to process "events"
    while True:             
        event, values = window.Read(timeout=1000) # timeout in ms for a GUI event
        #sg.Print(event, values) # reroute to separate debug window
        if event is None:   # window closed by cross icon
            try:
                rx_on_flag = False
                rx_flag = False
                tx_flag = False
                if p1.poll() is None:    # process still running
                    os.killpg(os.getpgid(p1.pid), signal.SIGINT)
                if p2.poll() is None:    # process still running
                    os.killpg(os.getpgid(p2.pid), signal.SIGINT)
            except Exception as E:
                pass
            break
        if event == '_usb_audio':
            try:
                alsa_card = values['_usb_audio']
                window.Element('_alsa_play').Update(alsa_card_dict[alsa_card][0])
                window.Element('_alsa_rec').Update(alsa_card_dict[alsa_card][1])
                window.Element('_alsa_play_vol').Update(alsa_card_dict[alsa_card][2])
                window.Element('_alsa_rec_vol').Update(alsa_card_dict[alsa_card][3])
                window.Element('_alsa_rec_ch').Update(alsa_card_dict[alsa_card][4])
            except Exception as E:
                #sg.Print('txt list error:',E)
                pass
        if event == 'Set Volume':
            try:
                # class alsaaudio.Mixer(control='Master', id=0, cardindex=-1, device='default')
                # Mixer.setvolume(volume, channel=None, pcmtype=PCM_PLAYBACK, units=VOLUME_UNITS_PERCENTAGE)
                # Mixer.getvolume(pcmtype=PCM_PLAYBACK, units=VOLUME_UNITS_PERCENTAGE)
                alsa_play_m = values['_alsa_play']
                alsa_rec_m = values['_alsa_rec']
                alsa_rec_ch_m = int(values['_alsa_rec_ch'])
                alsa_cardindex_m = int(values['_alsa_cardindex'])
                alsa_play_vol_m = int(values['_alsa_play_vol'])
                alsa_rec_vol_m = int(values['_alsa_rec_vol'])
                play = alsaaudio.Mixer(alsa_play_m, cardindex=alsa_cardindex_m)
                play.setvolume(alsa_play_vol_m)
                pvol = play.getvolume(0)    # arg. 0=PCM_PLAYBACK
                #sg.Print('playback volume: ',pvol)
                rec  = alsaaudio.Mixer(alsa_rec_m, cardindex=alsa_cardindex_m)
                #rec.setvolume(alsa_rec_vol_m)
                for ch in range(alsa_rec_ch_m):
                    rec.setvolume(alsa_rec_vol_m,ch,1)  # arg. 1=PCM_CAPTURE
                rvol = rec.getvolume(1) # arg. 1=PCM_CAPTURE
                #sg.Print('record volume: ',rvol)
                window.Element('_set_vol_msg').Update('OK play:'+str(pvol)+' '+'rec:'+str(rvol))
            except Exception as E:
                #sg.Print('Set Vol error:',E)
                window.Element('_set_vol_msg').Update('error')
        if event == 'TX':
            try:
                if tx_flag == False:
                    msg_start_str_m = values['_msg_start_str']
                    msg_stop_str_m = values['_msg_stop_str']
                    msg_call_str_m = values['_msg_call_str']
                    msg_rcv_str_m = values['_msg_rcv_str']
                    msg_start_count_m = int(values['_msg_start_count'])
                    call_sign_m = values['_call_sign']
                    rcv_sign_m = values['_rcv_sign']
                    baudrate_m = int(values['_baudrate'])
                    alsa_tx_conf_m = values['_alsa_tx_conf']        
                    msg_time_str_m = values['_msg_time_str']
                    msg_str = values['_tx_input']
                    timestamp = strftime('20%y%m%d_%H%M%S',localtime())
                    print timestamp+': '+'message transmission started'
                    tx_str = (msg_start_str_m+'\n')*msg_start_count_m+msg_call_str_m+call_sign_m+'\n'+msg_rcv_str_m+rcv_sign_m+'\n'+msg_time_str_m+timestamp+'\n'+msg_str+'\n'+msg_stop_str_m
                    #temp_path = os.path.join(tx_dir,'temp.txt')
                    #sg.Print('str: ',tx_str)
                    #with open(temp_path, 'wb') as tf:   # write in binary format, no EOL character modified
                    #    tf.write(tx_str.encode('utf-8'))    # default encoding is ascii
                    #tx_cmd = 'cat '+temp_path+' | minimodem --tx %d %s' %(baudrate_m,alsa_tx_conf_m)
                    tx_cmd = 'echo "%s" | minimodem --tx %d %s' %(tx_str,baudrate_m,alsa_tx_conf_m)
                    #sg.Print('command: ',tx_cmd)
                    #data = subprocess.check_output(tx_cmd, shell=True)    # blocking, wait until process returns
                    # (Linux) setsid creates a session and sets the process group ID if the calling process is not a process group leader
                    p1 = subprocess.Popen(tx_cmd, shell=True, preexec_fn=os.setsid) # non blocking, do not wait until process returns
                    tx_flag = True
            except Exception as E:
                #sg.Print('TX error:',E)
                pass
        if event == 'Stop TX':       
            try:
                if tx_flag == True:
                    tx_flag = False
                    timestamp = strftime('20%y%m%d_%H%M%S',localtime())
                    print timestamp+': '+'message transmission stopped'
                    if p1.poll() is None:    # process still running
                        # (Linux) getpgid gets the process group ID - equal to the process ID of the process that created the process group
                        os.killpg(os.getpgid(p1.pid), signal.SIGINT)  # Send Ctrl-C to process group
                        #sg.Print('stop TX process:',p1)
            except Exception as E:
                #sg.Print('Stop TX error:',E)
                pass
        if event == 'Clear':
            try:
                if p1.poll() is not None:   # process finished
                    window.Element('_tx_input').Update('')
            except Exception as E:
                window.Element('_tx_input').Update('')
        if event == '_txt_list':
            try:
                tx_dir_m = values['_tx_dir']
                txt_list = [i for i in os.listdir(tx_dir_m) if i.lower().endswith((".txt"))]
                window.Element('_txt_list').Update(sorted(txt_list))
                txt_file = values['_txt_list'][0]
                txt_path = os.path.join(tx_dir_m,txt_file)
                with open(txt_path, 'r') as tf:
                    msg_str = tf.read()
                window.Element('_tx_input').Update(msg_str)
            except Exception as E:
                #sg.Print('txt list error:',E)
                pass
        if event == 'RX':
            try:
                if rx_on_flag == False:
                    msg_start_str_m = values['_msg_start_str']
                    msg_call_str_m = values['_msg_call_str']
                    msg_rcv_str_m = values['_msg_rcv_str']
                    baudrate_m = int(values['_baudrate'])
                    alsa_rx_conf_m = values['_alsa_rx_conf']
                    rx_dir_m = values['_rx_dir']
                    call_sign_m = values['_call_sign']
                    rx_save_file = values['_rx_save_file']
                    rx_filter = values['_rx_filter']
                    timestamp = strftime('20%y%m%d_%H%M%S',localtime())
                    print timestamp+': '+'message reception started'
                    rx_cmd = 'minimodem --rx-one --quiet %d %s' %(baudrate_m,alsa_rx_conf_m)
                    #sg.Print('command: ',rx_cmd)
                    rx_on_flag = True
                    rx_flag = False
                    threading.Thread(target=rx_data_thread,args=(gui_queue,rx_dir_m,rx_cmd,msg_start_str_m,msg_call_str_m,msg_rcv_str_m,call_sign_m,rx_save_file,rx_filter)).start()
                    window.Element('_rx_msg').Update('RX ON')
            except Exception as E:
                #sg.Print('RX error:',E)
                pass
        if event == 'Stop RX':
            try:
                if rx_on_flag == True:
                    rx_on_flag = False
                    rx_flag = False
                    window.Element('_rx_msg').Update('RX OFF')
                    timestamp = strftime('20%y%m%d_%H%M%S',localtime())
                    print timestamp+': '+'message reception stopped'
                    if p2.poll() is None:    # process still running
                        os.killpg(os.getpgid(p2.pid), signal.SIGINT)  # Send Ctrl-C to  process group
                        #sg.Print('stop RX process:',p2)
            except Exception as E:
                #sg.Print('Stop RX error:',E)
                pass
        if tx_flag:
            try:
                if p1.poll() is not None:    # process finished
                    timestamp = strftime('20%y%m%d_%H%M%S',localtime())
                    print timestamp+': '+'message sent'
                    tx_flag = False
                    #sg.Print('tx_flag:',tx_flag)
            except Exception as E:
                #sg.Print('tx_flag error:',E)
                pass
        if rx_flag:
            try:
                message = gui_queue.get_nowait() # get_nowait() will get Queue.Empty exception when Queue is empty
                window.Element('_rx_input').Update(message)
                rx_single_trig = values['_rx_single_trig']
                if rx_single_trig:
                    rx_on_flag = False
                    rx_flag = False
                    window.Element('_rx_msg').Update('RX OFF')
                    timestamp = strftime('20%y%m%d_%H%M%S',localtime())
                    print timestamp+': '+'message reception stopped'
                else:
                    msg_start_str_m = values['_msg_start_str']
                    msg_call_str_m = values['_msg_call_str']
                    msg_rcv_str_m = values['_msg_rcv_str']
                    baudrate_m = int(values['_baudrate'])
                    alsa_rx_conf_m = values['_alsa_rx_conf']
                    rx_dir_m = values['_rx_dir']
                    call_sign_m = values['_call_sign']
                    rx_save_file = values['_rx_save_file']
                    rx_filter = values['_rx_filter']
                    rx_cmd = 'minimodem --rx-one --quiet %d %s' %(baudrate_m,alsa_rx_conf_m)
                    #sg.Print('command: ',rx_cmd)
                    rx_on_flag = True
                    rx_flag = False
                    threading.Thread(target=rx_data_thread,args=(gui_queue,rx_dir_m,rx_cmd,msg_start_str_m,msg_call_str_m,msg_rcv_str_m,call_sign_m,rx_save_file,rx_filter)).start()
                #sg.Print('rx message:',message)
                #sg.Print('rx_on_flag:',rx_on_flag)
                #sg.Print('rx_flag:',rx_flag)
            except Exception as E:
                #sg.Print('rx_flag error:',E)
                pass
                
    window.Close()

if __name__ == '__main__':
    gui()
    