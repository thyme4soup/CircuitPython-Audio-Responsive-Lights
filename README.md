# CircuitPython-Audio-Responsive-Lights
Audio responsive lights written in Circuitypython for the CPX board

## Overview

### Current State

The goal for this project is a lighting system that responds to sound (music or voice to speakers).
At the moment, it samples from the on-board microphone of the CPX board, which is noisy and can only
sample at 16khz for some reason. This is an issue because we have to handle a very large sample array (64 samples at least)
in order to get sub-1khz waves. The bass range is entirely sub-1khz, so we have to perform an FFT on 64 samples
and this gives us noticeable lag.

Once I have the materials I can set up the analog pin to read from an audio jack directly, so we can sample at a much lower rate
and (hopefully) have a quicker loop

### Setup and Testing

The code is built specifically for the CPX (circuit playground express) board at the moment, as it relies on some
library functions as well as hardware (lights, microphone) that are board-specific, but eventually it should
work on all CP boards.
