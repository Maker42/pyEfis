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

playing = False

""" WAV sample:
0000000: 5249 4646 eeba 0600 5741 5645 666d 7420  RIFF....WAVEfmt 
0000010: 1000 0000 0100 0100 44ac 0000 8858 0100  ........D....X..
0000020: 0200 1000 4c49 5354 1a00 0000 494e 464f  ....LIST....INFO
0000030: 4953 4654 0e00 0000 4c61 7666 3538 2e31  ISFT....Lavf58.1
0000040: 322e 3130 3000 6461 7461 a8ba 0600 0000  2.100.data......
"""

def aural_warning_loop(command_queue):
    global playing
    playback_device = alsaaudio.PCM()
    mixer = alsaaudio.Mixer()
    feed_thread = None
    playback_format = None
    playback_rate = None
    playback_channels = None
    while True:
        cmd = command_queue.get()
        if isinstance(cmd,str):
            if cmd.lower().startswith('q'):
                playing = False
                if feed_thread is not None:
                    feed_thread.join()
                    feed_thread = None
                return  # quit
            elif cmd.lower().startswith('stop'):
                playing = False
                if feed_thread is not None:
                    feed_thread.join()
                    feed_thread = None
        elif isinstance(cmd,tuple):
            cmd,args = cmd
            if cmd.lower().startswith('play'):
                args = (playback_device,args)
                feed_thread = threading.Thread(target=play_wav, args=args)
                playing = True
                feed_thread.start()
            elif cmd.lower().startswith('vol'):
                mixer.setvolume(args)
            elif cmd.lower().startswith('dev'):
                if len(args) == 1:
                    devname = args[0]
                    cardindex = -1
                elif len(args) == 1:
                    devname,cardindex = args
                playback_device = alsaaudio.PCM(device=devname,
                                cardindex=cardindex)
                mixer = alsaaudio.Mixer(device=devname,
                                cardindex=cardindex)

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

if __name__ == "__main__":
    # Unit testing
    import sys, queue
    path,vol,duration = sys.argv[1:]
    vol = int(vol)
    duration = float(duration)
    cmdq = queue.Queue()
    athread = threading.Thread(target=aural_warning_loop, args=(cmdq,))
    athread.start()
    cmdq.put(("vol", vol))
    cmdq.put(("play", path))
    time.sleep(duration)
    cmdq.put('stop')
    time.sleep(1)
    cmdq.put('quit')
    athread.join()
