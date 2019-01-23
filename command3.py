#!/usr/bin/env python
"""
Base data
data[0] Signal A (Red LED)
data[1] Signal B (Blue LED)

Extended data
data[2] Highpass Signal A (Red LED)
data[3] Highpass Signal B (Blue LED)
data[4] position (log(data[0]) - log(data[1]))
data[5] pressure ()(data[0] + data[1])/2)

"""


"""
Serial listener and command interpreter for Capacitive Touch
Sensor (CTS).
"""
from functools import wraps
from os import environ as env
from os.path import abspath, dirname, join
import time

import serial
from simpleaudio import WaveObject as Wav

import vlc
import glob

PORT = '/dev/cu.usbmodem12341' # hard-code for now...
BAUD = 115200

ASSETS_DIR = join(dirname(abspath(__file__)), 'assets')
AUDIO_MAP = dict(
    skip=vlc.MediaPlayer(join(ASSETS_DIR, 'skip.wav')),
    power_on=vlc.MediaPlayer(join(ASSETS_DIR, 'power_on.wav')),
    power_off=vlc.MediaPlayer(join(ASSETS_DIR, 'power_off.wav')),
    volume_up=vlc.MediaPlayer(join(ASSETS_DIR, 'volume_up.wav')),
    volume_down=vlc.MediaPlayer(join(ASSETS_DIR, 'volume_down.wav')),
    play=vlc.MediaPlayer(join(ASSETS_DIR, 'play.wav')),
)

# Data array indices
RED = 0
BLUE = 1
HP_RED = 2
HP_BLUE = 3
POS = 4
CAP = 5

ACTIVATE = 0.5
DEACTIVATE = -0.5
RED_POS = -0.05
BLUE_POS = -0.25

VOLUME_INTERVAL = 10
MIN_VOLUME = 0
MAX_VOLUME = 100
START_VOLUME = 50

WAIT_TIME = 2 # Seconds

MEDIA_DIR = join(dirname(abspath(__file__)), 'playlist')
playlist = glob.glob(join(MEDIA_DIR, '*.mp3'))

"""
Set up the media player
"""
instance = vlc.Instance('--verbose 9')
media_list = instance.media_list_new()
player = instance.media_player_new()
list_player = instance.media_list_player_new()
list_player.set_media_player(player)
list_player.set_media_list(media_list)
event_manager = list_player.event_manager()

"""
Set up the playlist
"""
media_list.lock()
for p in playlist:
    media = instance.media_new(p)
    media.parse()
    media_list.add_media(media)

media_list.unlock()
print(f'Loaded {media_list.count()} files')

sfx_instance = vlc.Instance()
sfx_media_list = sfx_instance.media_list_new()
sfx_player = sfx_instance.media_player_new()
sfx_list_player = sfx_instance.media_list_player_new()
sfx_list_player.set_media_player(sfx_player)
sfx_list_player.set_media_list(sfx_media_list)
sfx_event_manager = sfx_list_player.event_manager()


def diaper(function):
    """
    Prints exceptions
    """
    @wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception as ex:
            print(f'Exception occurred in {function.__name__}: {ex!r}')
    return wrapper


@diaper
def red_tap(player, current_volume):
    AUDIO_MAP['volume_down'].stop()
    AUDIO_MAP['volume_down'].play()

    if not current_volume:
        current_volume = player.audio_get_volume()

    if current_volume <= MIN_VOLUME:
        new_volume = MIN_VOLUME
    else:
        new_volume = current_volume - VOLUME_INTERVAL

    print(f'Volume Down: {current_volume}')
    player.audio_set_volume(new_volume)
    return new_volume


@diaper
def blue_tap(player, current_volume):
    AUDIO_MAP['volume_up'].stop()
    AUDIO_MAP['volume_up'].play()

    if not current_volume:
        current_volume = player.audio_get_volume()

    if current_volume >= MAX_VOLUME:
        new_volume = MAX_VOLUME
    else:
        new_volume = current_volume + VOLUME_INTERVAL

    print(f'Volume Up: {current_volume}')
    player.audio_set_volume(new_volume)
    return new_volume


@diaper
def center_tap(player): # Play the song
    """Middle double tap."""
    if player.is_playing():
        print('Pause')
        player.pause()
    else:
        print('Play')
        player.play()

    AUDIO_MAP['play'].stop()
    AUDIO_MAP['play'].play()


@diaper
def red_hold(player): # Play the song
    """Middle double tap."""
    player.previous()

    AUDIO_MAP['skip'].stop()
    AUDIO_MAP['skip'].play()


@diaper
def blue_hold(player): # Play the song
    """Middle double tap."""
    player.next()

    AUDIO_MAP['skip'].stop()
    AUDIO_MAP['skip'].play()


@diaper
def center_hold(player): # Play the song
    """Middle double tap."""
    if player.is_playing():
        print('Pause')
        player.pause()
    else:
        print('Play')
        player.play()

    AUDIO_MAP['play'].stop()
    AUDIO_MAP['play'].play()


@diaper
def main():
    """
    Connects to serial port and starts continous event loop.
    """
    current_blue_sample_count = 0
    current_red_sample_count = 0
    current_both_sample_count = 0
    off_counter = 0
    both_tap_count = 0
    connected = False
    being_held = False

    now = time.time()

    while not connected:
        try:
            print(f'Connecting to {PORT} ...')
            serial_com = serial.Serial(PORT, BAUD, timeout=10)
            connected = True
            print('Connected')
        except Exception as ex:
            print(f'Failed to connect: {ex!r}')
            sleep(1)

    current_volume = START_VOLUME
    player.audio_set_volume(START_VOLUME) # Set the volume
    pressed = False

    while True:
        data_str = serial_com.readline()
        data = data_str.split()
        try:
            red = float(data[RED])
            blue = float(data[BLUE])
            hp_red = float(data[HP_RED])
            hp_blue = float(data[HP_BLUE])
            pos = float(data[POS])
            cap = float(data[CAP])

        except IndexError:
            continue
        #print(f'{red}, {blue}, {hp_red}, {hp_blue}, {pos}, {cap}')

        highpass = hp_red + hp_blue


        if ( # Detect press
                highpass > ACTIVATE and
                pressed == False
        ):
            print('Press')
            pressed = True
            now = time.time() # Record the current system time

            if pos > RED_POS: # "Left" press
                current_volume = red_tap(player, current_volume)
            elif pos < BLUE_POS: # "Right" press
                current_volume = blue_tap(player, current_volume)
            else: # "Center" press
                center_tap(list_player)

        elif ( # Detect hold
                pressed == True and
                time.time() > now + WAIT_TIME
        ):
            print('Hold')
            pressed = False

            if pos > RED_POS: # "Left" hold
                current_volume = red_hold(list_player)
            elif pos < BLUE_POS: # "Right" hold
                current_volume = blue_hold(list_player)
                #else: # "Center" hold
                #center_hold(list_player) # Play/Pause

        elif ( # Detect release
                highpass < DEACTIVATE and
                pressed == True
        ):
            print('Release')
            pressed = False


if __name__ == '__main__':
    main()
