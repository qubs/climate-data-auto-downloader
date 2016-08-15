#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, json, psycopg2, requests, datetime, time
from sudecode.sudecode import decode

CONFIG_FILE_PATH = "./config.json"
MESSAGE_FILE_PATH = "./latest-messages.txt"

CENTURY_PREFIX = "20" # Hopefully this script won't be used in the 22nd century but just in case...

def main():
    with open(CONFIG_FILE_PATH, "rU") as configFile:
        config = json.loads(configFile.read())

        os.system("getDcpMessages -u {} -P {} -h {} -p {} -f ./st.sc -x > {}".format(
            config["lrgsConnection"]["username"],
            config["lrgsConnection"]["password"],
            config["lrgsConnection"]["host"],
            config["lrgsConnection"]["port"],

            MESSAGE_FILE_PATH
        ))

        with open(MESSAGE_FILE_PATH, "rU") as message_file:
            cleaned_message = message_file.read().strip() # TODO: Remove newlines

            message_headers = cleaned_message[:37]
            message_data = cleaned_message[37:]

            goes_id = message_headers[:8]

            # Format: YYYYDDDHHMMSS. Convert it to ISO 8601 for the API.
            arrival_time_text = message_headers[8:19]
            arrival_time_object = datetime.datetime.strptime(CENTURY_PREFIX + arrival_time_text, "%Y%j%H%M%S")

            message = {
                "goes_id": goes_id,
                "arrival_time": arrival_time_object.isoformat(),
                "failure_code": message_headers[19:20],
                "signal_strength": int(message_headers[20:22]),
                "frequency_offset": message_headers[22:24],
                "modulation_index": message_headers[24:25],
                "data_quality": message_headers[25:26],
                "goes_channel": int(message_headers[26:29]),
                "spacecraft": message_headers[29:30],
                "data_source": message_headers[30:32],
                "recorded_message_length": int(message_headers[32:37]),

                "values": decode(message_data, 3,
                    len(config["goesStations"][goes_id]["sensors"]),
                    config["goesStations"][goes_id]["numReadings"]
                ),

                "message_text": cleaned_message
            }

            print(message)

            # TODO: Process more (into readings, sensors, etc.)
            # TODO: Check for duplicate messages

            # Check for repeat messages.

            duplicate_exists = False

            try:
                r = requests.get(
                    "{}/messages/".format(config["apiConnection"]["url"]),
                    params={
                        "goes_id": message["goes_id"],
                        "start": arrival_time_object - datetime.timedelta(seconds=1),
                        "end": arrival_time_object + datetime.timedelta(seconds=1)
                    }
                )

                result = r.json()

                if len(result) > 0:
                    print("{}: The message already has been saved.".format(datetime.datetime.now().isoformat()))
                    duplicate_exists = True

            except requests.exceptions.Timeout:
                print("{}: Time-out while checking for duplicate messages.".format(datetime.datetime.now().isoformat()))

            except ValueError:
                print("{}: An invalid JSON response was recieved.".format(datetime.datetime.now().isoformat()))

            except requests.exceptions.RequestException as e:
                # Catch any generic request errors.

                print("{}: Error while checking for duplicate messages.".format(datetime.datetime.now().isoformat()))
                print(e)

            # If a duplicate doesn't exist, post the message to the API.

            if not duplicate_exists:
                times_to_repeat = 1
                cancel_next_repeat = False

                while times_to_repeat > 0:
                    times_to_repeat -= 1

                    try:
                        # Add message to database.

                        r = requests.post(
                            "{}/messages/".format(config["apiConnection"]["url"]),
                            data=message,
                            auth=(config["apiConnection"]["username"], config["apiConnection"]["password"])
                        )

                    except requests.exceptions.Timeout:
                        # Try a single retry.

                        if cancelNextRepeat:
                            times_to_repeat = 1
                            cancel_next_repeat = True

                            # Delay retry for 30 seconds to give the server some time to figure stuff out.
                            time.sleep(30)

                    except requests.exceptions.RequestException as e:
                        # Catch any generic request errors.

                        print("{}: Automatic download of data failed.".format(datetime.datetime.now().isoformat()))
                        print(e)

                        sys.exit(1)

if __name__ == "__main__":
    main()
