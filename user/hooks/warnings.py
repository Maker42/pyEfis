#!/usr/bin/env python3
#  Copyright (c) 2019 Garrett Herschleb
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

import time, struct
import threading
import alsaaudio
import serial

import pyavtools.fix as fix

playing = False

""" WAV sample:
0000000: 5249 4646 eeba 0600 5741 5645 666d 7420  RIFF....WAVEfmt 
0000010: 1000 0000 0100 0100 44ac 0000 8858 0100  ........D....X..
0000020: 0200 1000 4c49 5354 1a00 0000 494e 464f  ....LIST....INFO
0000030: 4953 4654 0e00 0000 4c61 7666 3538 2e31  ISFT....Lavf58.1
0000040: 322e 3130 3000 6461 7461 a8ba 0600 0000  2.100.data......
"""

class AuralWarnings:
    def __init__(self, config):
        self.aural_warnings = config['aural_warnings']

        if 'amixer' in config:
            mixer_control,mixer_id = config['amixer']
            self.mixer = alsaaudio.Mixer(control=mixer_control,id=mixer_id)
        else:
            self.mixer = alsaaudio.Mixer()

        if 'aplayer' in config:
            self.playback_devname,self.playback_index = config['aplayer']
        else:
            self.playback_devname,self.playback_index = (None,None)

        self.danger_item = fix.db.get_item("DANGER_LEVEL", create=True, wait=False)
        self.danger_item.valueChanged[float].connect(self.set_aural_warning)
        self.audio_playing = None
        self.audio_volume = None
        self.feed_thread = None

    def quit(self):
        self.stop()
        self.mixer = None

    def stop(self):
        global playing
        playing = False
        #print ("Stop playing")
        if self.feed_thread is not None:
            self.feed_thread.join()
            self.feed_thread = None
        self.audio_playing = None
        self.playback_device = None

    def play(self,path,vol):
        global playing
        if self.mixer is not None:
            if vol != self.audio_volume:
                self.mixer.setvolume(vol)
                self.audio_volume = vol
        if self.audio_playing is not None and path == self.audio_playing:
            return

        if playing:
            self.stop()
        if self.playback_devname is not None:
            self.playback_device = alsaaudio.PCM(device=playback_devname,
                            cardindex=playback_index)
        else:
            self.playback_device = alsaaudio.PCM()
        args = (self.playback_device,path)
        self.feed_thread = threading.Thread(target=play_wav, args=args)
        playing = True
        self.feed_thread.start()
        self.audio_playing = path

    def set_aural_warning(self, danger_level):
        print ("danger_level %.2g"%danger_level)
        if self.aural_warnings is not None:
            if danger_level > self.aural_warnings[0][0]:
                for level in range(1,len(self.aural_warnings)+1):
                    if danger_level > self.aural_warnings[-level][0]:
                        l,vol,path = self.aural_warnings[-level]
                        self.play(path,vol)
                        break
            else:
                self.stop()

def play_wav(device,path):
    global playing
    fd = open(path, 'rb')
    h = fd.read(4).decode('utf-8')
    if h != 'RIFF':
        fd.close()
        raise RuntimeError ("%s not a WAV file"%path)
    sztotal = fd.read(4)
    fmt_head = fd.read(8).decode('utf-8')
    if fmt_head != 'WAVEfmt ':
        fd.close()
        raise RuntimeError ("%s invalid WAV format"%path)
    fmt_size = fd.read(4)
    if fmt_size != bytes([0x10, 0,0,0]):
        fd.close()
        raise RuntimeError ("%s invalid format size"%path)
    st_wavfmt = struct.Struct("<HHIIHH")
    wavfmt,channels,rate,byterate,blockalign,bits_per_samp = \
            st_wavfmt.unpack(fd.read(16))
    bytes_sample = int(bits_per_samp / 8)
    #print ("WAV %d channels, %d Hz"%(channels, rate))

    if bytes_sample == 1:
        fmt = alsaaudio.PCM_FORMAT_U8
        #print ("WAV U8 samples")
    elif bytes_sample == 2:
        fmt = alsaaudio.PCM_FORMAT_S16_LE
        #print ("WAV S16 samples")
    elif bytes_sample == 3:
        fmt = alsaaudio.PCM_FORMAT_S24_LE
        #print ("WAV S24 samples")
    elif bytes_sample == 4:
        fmt = alsaaudio.PCM_FORMAT_S32_LE
        #print ("WAV S32 samples")
    else:
        raise RuntimeError("Unknown audio format. Cannot play")

    chunk_id = fd.read(4).decode('utf-8')
    while chunk_id != 'data':
        chunk_size = struct.unpack ("<I", fd.read(4))[0]
        if len(fd.read(chunk_size)) != chunk_size:
            fd.close()
            raise RuntimeError("EOF while reading chunk %s"%chunk_id)
        chunk_id = fd.read(4).decode('utf-8')
    data_begins = fd.tell()

    ideal_write_period = .1 # seconds
    frames_write = int(round(rate * ideal_write_period))
    write_period = float(frames_write) / float(rate)
    device.setformat(fmt)
    device.setrate(rate)
    device.setchannels(channels)
    bytes_write = bytes_sample * channels * frames_write
    device.setperiodsize(frames_write)
    # Write the first few chunks
    #print ('playing %s'%path)
    for i in range(3):
        adata = fd.read(bytes_write)
        if len(adata) < bytes_write:
            fd.close()
            raise RuntimeError("Audio file %s too small (%d)"%(path,i))
        n = device.write(adata)
        next_write_time = time.time() + write_period
        if n != frames_write:
            fd.close()
            raise RuntimeError("Audio device not accepting initial data (%d), code %d"%(i,n))

    while playing:
        adata = fd.read(bytes_write)
        if len(adata) < bytes_write:
            fd.seek(data_begins)
            adata = fd.read(bytes_write)
        sleep_time = next_write_time - time.time() - .1
        if sleep_time > 0:
            time.sleep(sleep_time)
        next_write_time += write_period
        n = device.write(adata)
        if n != frames_write:
            fd.close()
            raise RuntimeError("Audio device not accepting additional data")
    fd.close()
    return

class StickShaker:
    def __init__(self, config):
        self.ttyname = config['ss_ttyname']
        self.message = config['ss_message']
        self.multiplier = config['ss_multiplier']
        self.round_digits = config['ss_round_digits']
        self.danger_item = fix.db.get_item("DANGER_LEVEL",
                            create=True, wait=False)
        self.danger_item.valueChanged[float].connect(self.shake_stick)
        self.tty = serial.Serial(self.ttyname, config['ss_rate'], timeout=0)
        self.shake_val = 0

    def quit(self):
        self.tty.write (self.message.format(0))
        self.tty.close()
        self.tty = None

    def shake_stick(self, danger_level):
        val = round(danger_level * self.multiplier, self.round_digits)
        if val != self.shake_val:
            self.tty.write (self.message.format(val))
            self.shake_val = val

aobj = None
ssobj = None

def start(config):
    global aobj, ssobj
    aobj = AuralWarnings(config)
    if 'ss_ttyname' in config:
        ssobj = StickShaker(config)

def stop():
    global aobj, ssobj
    if aobj is not None:
        aobj.quit()
        aobj = None
    if ssobj is not None:
        ssobj.quit()
        ssobj = None
