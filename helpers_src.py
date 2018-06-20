import math

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