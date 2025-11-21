#!/usr/bin/env python3
"""
Validate a WAV file and wrap it in an MSU1 PCM header.
"""

import logging
import sys
import wave

from userOptions import Options

CHANNEL_NUMBER = 2
SAMPLE_WIDTH = 16 // 8
SAMPLE_RATE = 44100
COMPRESSION_TYPE = "NONE"
HEADER_MAGIC = b"MSU1"
RIFF_PCM_DATA = 44

logging.basicConfig(level=logging.INFO, format="%(message)s")


def main():
    options = Options(
        sys.argv,
        {
            "loopstart": {"value": 0, "type": "int", "max": 0xFFFFFFFF, "min": 0},
            "infile": {"value": "", "type": "str"},
            "outfile": {"value": "", "type": "str"},
        },
    )

    try:
        input_wave = wave.open(options.get("infile"), "rb")
    except IOError:
        logging.error('Unable to access input file "%s".' % options.get("infile"))
        sys.exit(1)

    validate_wave(input_wave)

    try:
        outFile = open(options.get("outfile"), "wb")
    except IOError:
        logging.error("Unable to access output file %s" % options.get("outfile"))
        sys.exit(1)

    with open(options.get("infile"), "rb") as inputFile:
        inputFile.seek(RIFF_PCM_DATA)
        outFile.write(HEADER_MAGIC)
        outFile.write(bytes((options.get("loopstart") & 0xFF,)))
        outFile.write(bytes(((options.get("loopstart") & 0xFF00) >> 8,)))
        outFile.write(bytes(((options.get("loopstart") & 0xFF0000) >> 16,)))
        outFile.write(bytes(((options.get("loopstart") & 0xFF000000) >> 24,)))
        outFile.write(inputFile.read())

    logging.info("Successfully wrote msu1 pcm audio file %s." % options.get("outfile"))


def validate_wave(inputFile):
    if CHANNEL_NUMBER != inputFile.getnchannels():
        logging.error(
            "Error, input file must have %s channels, but has %s."
            % (CHANNEL_NUMBER, inputFile.getnchannels())
        )
        sys.exit(1)

    if SAMPLE_WIDTH != inputFile.getsampwidth():
        logging.error(
            "Error, input file sample size must be %s Bit, but is %s Bit."
            % (SAMPLE_WIDTH * 8, inputFile.getsampwidth() * 8)
        )
        sys.exit(1)

    if SAMPLE_RATE != inputFile.getframerate():
        logging.error(
            "Error, input file sample rate must be %s Hz, but is %s Hz."
            % (SAMPLE_RATE, inputFile.getframerate())
        )
        sys.exit(1)

    if COMPRESSION_TYPE != inputFile.getcomptype():
        logging.error(
            "Error, input file compression must be of type %s, but is of type %s."
            % (COMPRESSION_TYPE, inputFile.getcomptype())
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
