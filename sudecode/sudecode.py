#!/usr/bin/env python3
# -*- coding: utf-8 -*-


SATLINK_DATA_BUFFER_EMPTY = "SATLINK DATA BUFFER EMPTY"


def decode(encoded_message, bytes_per_value, num_sensors, num_readings):
    message_start = 0

    # Get to the beginning of the message proper.
    while encoded_message[message_start] != "B":
        message_start += 1

    no_content = False

    # Check for an empty data buffer, which may get converted into "made-up" values.
    if SATLINK_DATA_BUFFER_EMPTY in encoded_message:
        no_content = True

    # group_id = encoded_message[message_start + 1]
    # time_offset = ord(encoded_message[message_start + 2]) - 64

    data_offset = message_start + 3
    initial_data_offset = data_offset
    decoded_data = []

    if not no_content:
        while data_offset < initial_data_offset + num_sensors * bytes_per_value * num_readings:
            if data_offset > len(encoded_message) - 1:  # Extra data on end, TODO: Extra data variable
                # Terminate early, this is an incomplete transmission.
                break

            data_bytes = encoded_message[data_offset:data_offset + bytes_per_value]

            # TODO: Allow for variable bytes per value

            no_value = False
            byte_offsets = [ord(x) - 64 for x in data_bytes]

            for i in range(len(data_bytes) - 1, -1, -1):
                if data_bytes[i] != "/":
                    break
                elif data_bytes[i] == "/" and i == 0:
                    no_value = True

            for i, byte in enumerate(byte_offsets):
                if byte < -1 or byte > 63:
                    no_value = True

            if not no_value:
                # The value can be considered 'valid' for the purposes of the decoder.

                # The pseudobinary format sends the value 127 (ASCII delete) as a question mark (63) instead.
                # We move them back up to their correct numerical value.
                for i, byte in enumerate(byte_offsets):
                    if byte == -1:
                        byte_offsets[i] = 63

                numerical_value = 0
                for i in range(len(data_bytes) - 1, -1, -1):
                    numerical_value += byte_offsets[i] * 2 ** ((len(data_bytes) - i - 1) * 6)

                if numerical_value > (2 ** (bytes_per_value * 6) // 2) - 1:
                    # i.e. is a negative number in two's complement
                    numerical_value = -1 * (2 ** (bytes_per_value * 6) - numerical_value)

                decoded_data.append(numerical_value)
            else:
                decoded_data.append(None)  # None represents a blank field here

            data_offset += bytes_per_value

    return decoded_data


def main():
    while True:
        message = input()
        print(decode(message, 3, 9, 4))

if __name__ == "__main__":
    main()
