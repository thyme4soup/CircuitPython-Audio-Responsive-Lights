import time
import microcontroller
import array
from analogio import AnalogIn
import board
import audiobusio
from adafruit_circuitplayground.express import cpx
import math
'''
TODO:
  + Deal with precision loss on time.monotonic() after long periods of runtime
    + Minor fix is added by resetting the board during the first idle period after 24 hours.
      Expected precision loss is +- 4ms by the time of the reset, which translates to
      only a minor loss in accuracy when we eventually handle audio sampling directly
  + Faster fft (maybe move methods to mpy file?)
'''


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
    s = cur_time()
    if i < 10:
        cpx.pixels[i % 10] = (int(255 - (255 * i / 10)), 0, int(255 * i / 10))
    else:
        cpx.pixels[i % 10] = (0, int(255 * (i - 10) / 10), int(255 - (255 * (i - 10) / 10)))
    cpx.pixels[(i - 1) % 10] = OFF
    while cur_time() - s < (STARTUP_DURATION / 20):
        pass
cpx.pixels.fill(OFF)
########## End startup animation

########## FFT Functions
# This is a reimplementation of numpy.fft.fftfreq for circuitpython
def fftfreq(n, d=1.0):
    freqs = [0]*n
    if n%2 == 0:
        for i in range(n/2): # from 0 to n/2 - 1
            freqs[int(i)] = i / (d*n)
        for i in range(-n/2, 0): # from -n/2 to -1
            freqs[int(n + i)] = i / (d*n)
    else:
        for i in range((n-1)/2 + 1): # from 0 to (n-1)/2
            freqs[int(i)] = i / (d*n)
        for i in range(-(n-1)/2, 0): # from -(n-1)/2 to -1
            freqs[int(i)] = 0 #idk lmao who uses odd numbers of samples, I cut this out anyways
    return freqs
    
# This is an fft algo pulled from https://github.com/peterhinch/micropython-fft
def fft(nums, forward=True, scale=False):
    n = len(nums)
    m = int(math.log(n) / math.log(2))
    i2 = n >> 1
    j = 0
    for i in range(n-1):
        if i<j: nums[i], nums[j] =  nums[j], nums[i]
        k = i2
        while (k <= j):
            j -= k
            k >>= 1
        j+=k
    #Compute the FFT
    c = 0j-1
    l2 = 1
    for l in range(m):
        l1 = l2
        l2 <<= 1
        u = 0j+1
        for j in range(l1):
            for i in range(j, n, l2):
                i1 = i+l1
                t1 = u*nums[i1]
                nums[i1] = nums[i] - t1
                nums[i] += t1
            u *= c
        ci = math.sqrt((1.0 - c.real) / 2.0) # Generate complex roots of unity
        if forward: ci=-ci                   # for forward transform
        cr = math.sqrt((1.0 + c.real) / 2.0) # phi = -pi/2 -pi/4 -pi/8...
        c = cr + ci*1j#complex(cr,ci)
    # Scaling for forward transform
    if (scale and forward):
        for i in range(n):
            nums[i] /= n
    return nums 

# END pull (didn't use the full library bc it required cmath)
########## End FFT Functions

########## Main Code
analogin = AnalogIn(board.A1)

def getVoltage(pin):
    return (pin.value * 3.3) / 65536

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

frq = 16000
sub_bass_range = 20
low_range = 500
mid_range = 1000
high_range = 4000
samples = 64

freqs = fftfreq(samples)[:int(samples/2)]

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
        while freqs[i] * freq < sub_bass_range and i < len(freqs):
            i += 1
        
        while freqs[i] * freq < low_range and i < len(freqs):
            low = max(low, mags[i])
            i += 1
        
        while freqs[i] * freq < mid_range and i < len(freqs):
            mid = max(mid, mags[i])
            i += 1
        
        while freqs[i] * freq < high_range and i < len(freqs):
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

def handleReset():
    global idle_start
    if current != (0, 0, 0, 0):
        idle_start = cur_time()
    if cur_time() - startup_monotonic > RESTART_THRESHOLD and cur_time() - idle_start > IDLE_THRESHOLD:
        microcontroller.reset()

#freqs = [0., 0.125, 0.25, 0.375, -0.5, -0.375, -0.25, -0.125]
mic = audiobusio.PDMIn(board.MICROPHONE_CLOCK, board.MICROPHONE_DATA, frequency=frq, bit_depth=16)

while True:
    start = time.monotonic()
    nums = [0] * samples
    
    ''' This snippet is for analog reading on a pin rather than the mic
    This can be viable considering both of these:
        https://github.com/adafruit/circuitpython/issues/484
        https://github.com/adafruit/circuitpython/issues/487
    for i in range(samples):
        voltage = getVoltage(analogin)
        nums[i] = voltage
    '''
    
    # Record and convert into 'nums' (frequency magnitudes)
    mic_read = array.array('H', [0] * samples)
    mic.record(mic_read, len(mic_read))
    nums = [float(x) for x in mic_read]
    
    # Perform fft and cut it down to size (the result is mirrored)
    fft(nums)
    
    del nums[0]
    del nums[len(nums) // 2:]
    for i in range(len(nums)):
        nums[i] = abs(nums[i])
    
    # Then we handle the result in a separate function
    setLights(nums, frq)
    
    # Handle the reset for monotonic after handling input
    handleReset()
    
    # Normally we would include a sleep, but the loop is slow enough as is.
    duration = time.monotonic() - start
    print("done in {}ms".format(1000 * duration))

########## End Main Code