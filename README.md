# Audio modem interface for Walkie-Talkie

## Objective
I wanted to build a simple off-the-grid communication system that can be assembled with common off-the-self parts.  
I programmed a Python GUI to interface with the [minimodem](http://www.whence.com/minimodem/) Linux tool, running on a RaspberryPi.  
Minimodem use FSK modulation to transmit messages over the  audio band.  
The messages can be transmitted by walkie-talkie over a few kilometers (I used a Baofeng UV-5R for my tests).  
This is an old project programmed in Python 2.7, I have since moved on to [Meshtastic](https://meshtastic.org/).  

## Python code
The Python GUI was tested on a raspberryPi 3B+ with Raspbian10.  
The GUI is programmed with the library PySimpleGUI.  
There are 3 tabs, TX panel, RX panel, config panel.  
  
![alt text](https://github.com/carpet852/Audio_modem/blob/main/python/minimodem_gui.png)  
  
Python librairies to install:
```
$ sudo apt-get install minimodem
$ sudo apt-get install python-alsaaudio
$ sudo pip install PySimpleGUI27
```

## Hardware
- RaspberryPi. A low power model is preferable. see [here](https://www.pidramble.com/wiki/benchmarks/power-consumption).
- [RTC module](https://www.aliexpress.com/item/1005003707505154.html) connected to Raspberry Pi I2C bus (x4 2.54mm cables).
- USB power bank & USB cable to power the RaspberryPi in the field.
- [Baofeng UV-5R](https://en.wikipedia.org/wiki/Baofeng_UV-5R) low-cost 5W FM walkie-talkie.  
  Please do note that in many countries, it is illegal to use a transmitter >0.5W without a proper radio amateur license.
- [Nagoya NA-771](https://baofengtech.com/product/nagoya-na-771/) 144/430 MHz Whip antenna that have better gain than the Baofeng stock antenna.
Be careful to select the version with SMA female connector. There are also fake models on AliExpress that have a less than ideal S11.
- USB Sound Card to be connected to cable. I tested the [UGREEN USB audio sound card](https://www.aliexpress.com/item/4001299124074.html) and the [IC is recognized by Raspbian](https://github.com/carpet852/Audio_modem/blob/main/hardware/UGREEN_usb_audio.png).
- Custom-built [cable](https://github.com/carpet852/Audio_modem/blob/main/hardware/IMG_2892.jpg) to connect the RaspberryPi to a walkie-talkie.
I cut and soldered the Baofeng Mic cable to a TRRS audio jack connector.
I designed and 3D-printed a simple cylinder to enclose the TRRS jack and filled it with holt-melt glue.

## Audio config
Baofeng UV-5R: need to activate the VOX (cf manual).
I found VOX level 2 to be good enough.  
UGREEN USB Sound Card levels: output PCM 40, input MIC 85.  
Adjust output/input levels to prevent signal clipping and trigger VOX on walkie-talkie.  
Attention: audio levels need to be adjusted in the audio mixer each time the sound card is plugged!  
The Python GUI has a button to calibrate the audio levels automatically.  
  
Some commands
```
set default audio device to 3.5mm audio jack or USB adaptor
$ sudo raspi-config > advanced options > audio

audio mixer
$ alsamixer

list usb devices
$ lsusb -t

list playback devices
$ aplay -l

list capture devices
$ arecord -l
```

## WiFi AP and VNC server
The RaspberryPi needs to be configured as a [WiFi Access Point](https://thepi.io/how-to-use-your-raspberry-pi-as-a-wireless-access-point/), and the [VNC server](https://www.ionos.com/digitalguide/server/configuration/setting-up-virtual-network-computing-on-raspberry-pi/) needs to be activated in Raspbian.
The Raspberry Pi can be accessed from your phone using any VNC client app.  

## Webserver
I added a simple [lighttpd webserver](https://mike632t.wordpress.com/2020/04/10/installing-lighttpd-with-support-for-python-scripts/) to be able to read/write messages directly from the browser on my phone.  
A simple index.html page with a Python CGI script is running on the Raspberry Pi.  
  
Some commands
```
edit config file:
# sudo gedit /etc/lighttpd/lighttpd.conf
restart server:
# sudo service lighttpd force-reload
start server:
# sudo service lighttpd start
# sudo service lighttpd stop
check conf file: lighttpd -t -f /etc/lighttpd/lighttpd.conf
enable server at boot:
# systemctl status lighttpd
# sudo systemctl enable lighttpd
# sudo systemctl disable lighttpd
error log:
# sudo less /var/log/lighttpd/error.log
```

## RTC module
A RTC module can be added to keep track of time since the RapsberryPi is not supposed to be connected to the internet.  
I bought a [DS3231](https://www.analog.com/en/products/ds3231.html) RTC module with battery and I connected it to the I2C bus on the raspberry Pi.  
[Adafruit RTC tutorial](https://learn.adafruit.com/adding-a-real-time-clock-to-raspberry-pi/set-rtc-time)  
  
Some commands
```
RTC module ds3231 setup (need raspbian with systemd)
0. install i2c libraries
    $ sudo apt-get install python-smbus i2c-tools
1. add support for the RTC module
    $ sudo vi /boot/config.txt => add at the end of the file: dtoverlay=i2c-rtc,ds3231
    $ sudo reboot
    $ sudo i2cdetect -y 1 => should see UU at address 0x68
2. Disable the fake hwclock which interferes with the real hwclock
    $ sudo apt-get -y remove fake-hwclock
    $ sudo update-rc.d -f fake-hwclock remove
    $ sudo systemctl disable fake-hwclock
3. start the real hwclock
    $ sudo vi /lib/udev/hwclock-set => comment out the following lines:
        #if [ -e /run/systemd/system ] ; then
        # exit 0
        #fi
        #/sbin/hwclock --rtc=$dev --systz --badyear
        #/sbin/hwclock --rtc=$dev --systz
4. set and read the time of the hwclock-set
    $ sudo hwclock -w   => write system time to rtc
    $ sudo hwclock -r   => read time from rtc
    $ sudo hwclock -s   => set system time from rtc
    # date              => read system time
    $ sudo reboot
```

## Field test checklist
Field test photo [here](https://github.com/carpet852/Audio_modem/blob/main/field%20test/001.JPG) 
- UV-5R: activate VOX 2
- UV-5R: set VOLUME around 1/3 of full volume
- power on the RPI using the battery pack
- connect USB audio adaptor to RPI first, then to UV-5R
- connect to RPI WiFi AP, then to RPI VNC server
- launch minimodem_gui.py > Config > Set Volume (needs to be done each time the USB audio adaptor is disconnected)

