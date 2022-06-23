#!/usr/bin/python3
# ZR6TG - Tom - 2022/06/23

# basic signals detection code ported from https://github.com/m0dts/QO-100-WB-Live-Tune

import asyncio
import pygame
import websockets
import os
from  datetime import datetime
import pygame.gfxdraw
#os.environ["SDL_FBDEV"] = "/dev/fb0"

# CONFIGURATION
FFT_URL = "wss://eshail.batc.org.uk/wb/fft" #official batc fft
#FFT_URL = "ws://192.168.0.244:7681"

CALLSIGN = "ZR6TG"
COL_BG = (20, 29, 43)
COL_SPECTRUM = (217, 127, 43)
COL_TEXT = (224,224,224)

WIDTH = 800
HEIGHT = 480

class Clock:
    def __init__(self, time_func=pygame.time.get_ticks):
        self.time_func = time_func
        self.last_tick = time_func() or 0
 
    async def tick(self, fps=0):
        if 0 >= fps:
            return
 
        end_time = (1.0 / fps) * 1000
        current = self.time_func()
        time_diff = current - self.last_tick
        delay = (end_time - time_diff) / 1000
 
        self.last_tick = current
        if delay < 0:
            delay = 0
 
        await asyncio.sleep(delay)

class Graphics:
 
    def __init__(self, width, height):
        self.start_freq = 10490.5
        self.width =  width
        self.height = height
        self.x_tab = (self.width-50) /922
        self.font = pygame.font.SysFont('freesans', 20)
        self.bigfont = pygame.font.SysFont('freesans', 180)
        self.mediumfont = pygame.font.SysFont('freesans', 50)


    def align_symbolrate(self, width):
        if width < 0.002: return 0
        if width < 0.065: return 0.035
        if width < 0.086: return 0.066
        if width < 0.195: return 0.125
        if width < 0.277: return 0.250
        if width < 0.388: return 0.333
        if width < 0.700: return 0.500
        if width < 1.2: return 1.0
        if width < 1.6: return 1.5
        if width < 2.2: return 2
        
        return int(width)

    async def find_signals(self, fft_data):
        signals = []
        i = 0
        j = 0
        noise_level = 11000
        signal_threshold = 18000
        in_signal = False
        start_signal = 0
        end_signal = 0
        mid_signal = 0
        signal_strength = 0
        signal_bw = 0
        signal_freq = 0
        acc = 0
        acc_i = 0

        i = 2
        while i < len(fft_data):

            if in_signal == False:
                if (fft_data[i] + fft_data[i-1] + fft_data[i-2]) / 3 > signal_threshold:
                    in_signal = True
                    start_signal = i
            else:
                if (fft_data[i] + fft_data[i-1] + fft_data[i-2]) / 3 < signal_threshold:
                    in_signal = False
                    end_signal = i

                    acc = 0
                    acc_i = 0

                    j = int(start_signal + (0.3 * ( end_signal - start_signal )))

                    while ( j < start_signal + (0.8 * (end_signal - start_signal))):
                        acc = acc + fft_data[j]
                        acc_i = acc_i + 1
                        j+=1

                    if acc_i == 0:
                        in_signal = False
                        continue

                    signal_strength = acc / acc_i

                    # find real start
                    j = start_signal 
                    while (fft_data[j] - noise_level) < 0.75 * (signal_strength - noise_level):
                        start_signal = j
                        j+=1

                    # find real end
                    j = end_signal
                    end_signal_orig = j
                    while (fft_data[j] - noise_level) < 0.75 * (signal_strength - noise_level):                        
                        end_signal = j

                        if j <= 0:
                            end_signal = end_signal_orig
                            fake_end = True
                            break
                        j -= 1


                    mid_signal = start_signal + ((end_signal - start_signal)/2)
                    signal_freq = self.start_freq + (((mid_signal + 1) / (len(fft_data)) * 9))
                    signal_bw = self.align_symbolrate((end_signal - start_signal) * (9 / len(fft_data)))

                    if signal_bw >= 0.033:
                        signals.append({'start': start_signal, 'end' : end_signal, 'mid' : mid_signal, 'freq' : signal_freq, 'signal_strength' : signal_strength/255, 'signal_bw' : signal_bw})



            i += 1

        return signals


    async def update(self, window, fft):
        polygon_data = []
        fft_data = []
        x = 0

        while ( x < len(fft)-1 ):
            db = [fft[x],fft[x+1]]
            #y = int.from_bytes(db, 'little')/255
            fft_data.append(int.from_bytes(db, 'little'))
            polygon_data.append((25 + (x/2 * self.x_tab),480-int.from_bytes(db, 'little')/255))
            x += 2

        signals = await self.find_signals(fft_data)

        polygon_data.append((25,480))
        pygame.gfxdraw.filled_polygon(window, polygon_data,COL_SPECTRUM)
        pygame.gfxdraw.aapolygon(window, polygon_data,(197,244,103))

        # show time
        #timeStr = datetime.now().strftime("%H:%M:%S")
        timeStr = datetime.now().strftime("%H:%M")

        text_width, text_height = self.bigfont.size(timeStr)
        text = self.bigfont.render(timeStr, True, COL_TEXT)
        window.blit(text, (400 - text_width/2, 80))

        dateStr = datetime.now().strftime("%m/%d")
        
        text_width, text_height = self.bigfont.size(dateStr)
        text = self.mediumfont.render(dateStr, True, COL_TEXT)
        window.blit(text, (665 ,5))

        # show callsign
        text_width, text_height = self.bigfont.size(CALLSIGN)
        text = self.mediumfont.render(CALLSIGN, True, COL_TEXT)
        window.blit(text, (5 ,5))

        for sig in signals:
            text_width, text_height = self.font.size(str(round(sig['freq'],2)))
            text = self.font.render(str(round(sig['freq'],2)) + "", True, COL_TEXT)
            window.blit(text, (25 + (int(sig['mid']) * self.x_tab) - text_width/2, 480 - int(sig['signal_strength']) - 60))
            text_width, text_height = self.font.size(str(int(sig['signal_bw'] * 1000)) + "Ks")

            text = self.font.render(str(int(sig['signal_bw'] * 1000)) + "Ks", True, COL_TEXT)
            window.blit(text, (25 + (int(sig['mid']) * self.x_tab) - text_width/2, 480 - int(sig['signal_strength']) - 40))

 
class Socket:
    def __init__(self):
        self.websocket = None

    async def startup(self):
        self.websocket = await websockets.connect(FFT_URL)

    async def updateFFT(self):
        return await self.websocket.recv()

async def main():
    
    window = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.mouse.set_visible(False)

    graphics = Graphics(WIDTH, HEIGHT)
    clock = Clock()
    socket = Socket()
    await socket.startup()

    while True:

        fft = await socket.updateFFT()
        window.fill(COL_BG)
        await graphics.update(window, fft)
        pygame.display.flip()
 
        await clock.tick(30)
 
 
if __name__ == "__main__":
    pygame.init()
    asyncio.run(main())
    pygame.quit()