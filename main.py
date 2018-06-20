import time
import microcontroller
import array
from analogio import AnalogIn
import board
import audiobusio
from adafruit_circuitplayground.express import cpx
import helpers
import gc

# Fiddling with things to fix time precision loss
IDLE_THRESHOLD    = 15         # s until we determine that the speaker is idle (15 seconds)
RESTART_THRESHOLD = 86400      # s until time.monotonic() is due for a reset (24 hours)
def cur_time():
    return time.monotonic()
startup_monotonic = cur_time() # the monotonic start of our reset
idle_start        = cur_time() # the monotonic of the last meaningful update

# Base colors
WHITE = (50, 50, 50)
RED   = (220, 0, 0)
OFF   = (0,   0,  0)

########## Startup animation
print("startup")
cpx.pixels.brightness = 0.1
STARTUP_DURATION = 1
for i in range(20):
    if i < 10:
        cpx.pixels[i % 10] = (int(255 - (255 * i / 10)), 0, int(255 * i / 10))
    else:
        cpx.pixels[i % 10] = (0, int(255 * (i - 10) / 10), int(255 - (255 * (i - 10) / 10)))
    cpx.pixels[(i - 1) % 10] = OFF
    while cur_time() - startup_monotonic < i * (STARTUP_DURATION / 20):
        pass
cpx.pixels.fill(OFF)
########## End startup animation

########## Main Code
analogin = AnalogIn(board.A0)

brightness_attack = 0.4
brightness_fade = 0.1

# Assignments are low, medium, high
color_attack = (10, 4, 6)
color_fade = (10, 4, 7)
color_threshold = 8

# Brightness, Low, Med, High
current = (0, 0, 0, 0)

# The threshold lowers during music and climbs during idle periods
# The dynamic sensitivity avoids false flashing and allows for sensitivity during quiet songs
THRESHOLD_H = 4.0
THRESHOLD_L = 1.5
threshold_gain_loss = (THRESHOLD_H - THRESHOLD_L, 0.1)
threshold = THRESHOLD_H
maxed = 1.0

frq = 8000
sub_bass_range = 20
low_range = 500
mid_range = 1000
high_range = 3000
samples = 32

freqs = helpers.fftfreq(samples)

# To avoid flashing we use a modified attack/fade based in part on a reactive lighting system by Jared
# (reference http://jared.geek.nz/2013/jan/sound-reactive-led-lights)
def shift_to_target(brightness, colors):
    global current
    b, lo, med, hi = current
    
    if b < brightness:
        b = min(b + brightness_attack, maxed)
    elif b > brightness:
        b = max(b - brightness_fade, 0)
    
    if lo < colors[0]:
        lo = min(lo + color_attack[0], 254)
    elif colors[0] < lo:
        lo = max(lo - color_fade[0], 0)
    
    if med < colors[1]:
        med = min(med + color_attack[1], 254)
    elif colors[1] < med:
        med = max(med - color_fade[1], 0)

    if hi < colors[2]:
        hi = min(hi + color_attack[2], 254)
    elif colors[2] < hi:
        hi = max(hi - color_fade[2], 0)
    
    # Update our current lighting
    current = (b, lo, med, hi)

def setLights(mags, freq):
    low, mid, high = 0, 0, 0
    global threshold
    
    brightness_appraisal = max(mags) / 1000
    if brightness_appraisal - threshold < 0:
        brightness = 0.0
        # See threshold_gain_loss declaration for dynamic threshold explanation
        # Note that if the volume is under the threshold we shift towards no color as well
        threshold = min(threshold + threshold_gain_loss[1], THRESHOLD_H)
    else:
        brightness = maxed
        threshold = max(threshold - threshold_gain_loss[0], THRESHOLD_L)
        
        i = 0
        while freqs[i] * freq <= sub_bass_range and i < len(mags):
            i += 1
        
        while freqs[i] * freq <= low_range and i < len(mags):
            low = max(low, mags[i])
            i += 1
        
        while freqs[i] * freq <= mid_range and i < len(mags):
            mid = max(mid, mags[i])
            i += 1
        
        while freqs[i] * freq <= high_range and i < len(mags):
            high = max(high, mags[i])
            i += 1
        
        # reduce one value to 0 to prevent overly 'white' lighting
        base = min(low, mid, high)
        low -= base
        mid -= base
        high -= base
        # then we scale to 255, getting a major color and a minor color
        cap = max(low, mid, high)
        low = 254 * low / max(cap, 1)
        mid = 254 * mid / max(cap, 1)
        high = 254 * high / max(cap, 1)
    
    
    shift_to_target(brightness, (low, mid, high))

    # The goal here is to reimplement with a string of LEDs. Additionally, the cpx library
    # seems to be pretty slow, so it might be beneficial to start handling the lights directly
    
    cpx.pixels.brightness = current[0] # Set brightness (which is keyed to the first array index)
    
    # The assignment goes from low to high with index, so 1, 2, 3 means red low, green med, blue high
    cpx.pixels.fill((current[1], current[3], current[2]))
    #print(current)

def handleReset():
    global idle_start
    if current != (0, 0, 0, 0):
        idle_start = cur_time()
    if cur_time() - startup_monotonic > RESTART_THRESHOLD and cur_time() - idle_start > IDLE_THRESHOLD:
        microcontroller.reset()

mic = audiobusio.PDMIn(board.MICROPHONE_CLOCK, board.MICROPHONE_DATA, frequency=16000, bit_depth=16)

while True:
    start = cur_time()
    
    ''' This snippet is for analog reading on a pin rather than the mic
    This can be viable considering both of these:
        https://github.com/adafruit/circuitpython/issues/484
        https://github.com/adafruit/circuitpython/issues/487
    for i in range(samples):
        nums[i] = analogin.value
        #print(nums[i])
    duration = cur_time() - start
    for i in range(samples):
        nums[i] = nums[i] // 65536
    print(duration)
    frq = samples / duration
    '''
    
    # Record and convert into 'nums' (frequency magnitudes)
    mic_read = array.array('H', [0] * (samples * 2))
    mic.record(mic_read, len(mic_read))
    nums = [float(x) for x in mic_read]
    del mic_read
    nums = nums[::2]   # cut out every other sample to get target freq
    #print(nums)
    helpers.fft(nums)
    del nums[0]
    del nums[len(nums) // 2:]
    for i in range(len(nums)):
        nums[i] = abs(nums[i])
    
    # Then we handle the result in a separate function
    setLights(nums, frq)
    
    # Handle the reset for monotonic after handling input
    handleReset()
    
    duration = cur_time() - start
    # Normally we would include a sleep, but the loop is slow enough as is.
    #print("done in {}s".format(duration))
    #print(gc.mem_free())
    del nums

########## End Main Code