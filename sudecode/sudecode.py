#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, json, math

configPath = "../config.json"

def decode(encodedMessage, bytesPerValue, numSensors, numReadings):
    messageStart = 0

    # Get to the beginning of the message proper.
    while encodedMessage[messageStart] != "B":
        messageStart += 1

    groupId = encodedMessage[messageStart + 1]
    timeOffset = ord(encodedMessage[messageStart + 2]) - 64

    dataOffset = messageStart + 3
    initialDataOffset = dataOffset
    decodedData = []

    # TODO: Handle negative numbers.

    while dataOffset < initialDataOffset + numSensors * bytesPerValue * numReadings:
        if dataOffset > len(encodedMessage) - 1: # Extra data on end, TODO: Extra data variable
            # Terminate early, this is an incomplete transmission.
            break

        bytes = encodedMessage[dataOffset:dataOffset + bytesPerValue]

        # TODO: Allow for variable bytes per value

        noValue = False
        byteOffsets = [ord(x) - 64 for x in bytes]

        for i in range(len(bytes) - 1, -1, -1):
            if bytes[i] != "/":
                break
            elif bytes[i] == "/" and i == 0:
                noValue = True

        for i, byte in enumerate(byteOffsets):
            if byte < -1 or byte > 63:
                noValue = True

        if not noValue:
            # The pseudobinary format sends the value 127 (ASCII delete) as a question mark (63) instead.
            # We move them back up to their correct numerical value.
            for i, byte in enumerate(byteOffsets):
                if byte == -1:
                    byteOffsets[i] = 63

            numericalValue = 0
            for i in range(len(bytes) - 1, -1, -1):
                numericalValue += byteOffsets[i] * 2 ** ((len(bytes) - i - 1) * 6)

            if numericalValue > (2 ** (bytesPerValue * 6) / 2) - 1: # i.e. is a negative number in two's complement
                numericalValue = -1 * (2 ** (bytesPerValue * 6) - numericalValue)

            decodedData.append(numericalValue)
        else:
            decodedData.append(None) # None represents a blank field here

        dataOffset += bytesPerValue

    return decodedData

def main():
    with open(configPath, "rU") as configFile:
        configData = json.load(configFile)

        while True:
            message = input()
            print(decode(message, 3, 9, 4))

if __name__ == "__main__":
    main()
