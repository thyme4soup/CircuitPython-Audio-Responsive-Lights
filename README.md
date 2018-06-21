# CircuitPython-Audio-Responsive-Lights
Audio responsive lights written in Circuitypython for the CPX board

## Overview

### Current State

#### v1.0

The goal for this project is a lighting system that responds to sound (music or voice to speakers).
At the moment, it samples from the on-board microphone of the CPX board, which is noisy and can only
sample at 16khz for some reason. This is an issue because we have to handle a very large sample array (64 samples at least)
in order to get sub-1khz waves. The bass range is entirely sub-1khz, so we have to perform an FFT on 64 samples
and this gives us noticeable lag.

Once I have the materials I can set up the analog pin to read from an audio jack directly, so we can sample at a much lower rate
and (hopefully) have a quicker loop

#### v2.0

We're still sampling from the microphone directly. However, I've modified the code to take double the samples and cut it down by half, effectively getting us to an 8khz sample rate. This lets us take fewer samples total (as we can actually detect sub-1khz waves without increasing samples size), and thus speeds up the main program loop. Now, we loop in about 150 ms which gives much smoother lighting.

### Setup and Testing

The code is built specifically for the CPX (circuit playground express) board at the moment, as it relies on some
library functions as well as hardware (lights, microphone) that are board-specific.
The program uses .mpy to reduce memory usage, which in this project is tied to Circuitpython 2.x. However, the source of helpers.mpy is provided as helpers-src.py, so you can rebuild helpers.mpy for 3.x. Alternatively, you can try re-naming helpers-src.py to helpers.py. This may cause memory issues, but if your board has more space than the cpx you might be fine.
