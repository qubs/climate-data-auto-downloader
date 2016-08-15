#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#   Copyright 2016 the Queen's University Biological Station

#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at

#       http://www.apache.org/licenses/LICENSE-2.0

#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import os, sys, json, requests, datetime, time, pprint
from sudecode.sudecode import decode

CONFIG_FILE_PATH = "./config.json"
SEARCH_FILE_PATH = "./st.sc"
MESSAGE_FILE_PATH = "./latest-messages.txt"

GOES_DATA_CHANNEL = 19 # Default
CENTURY_PREFIX = "20"  # Default, hopefully this script won't be used in the 22nd century but just in case...

pp = pprint.PrettyPrinter(indent=2, compact=True) # For nice log file output and debugging.

def main():
    with open(CONFIG_FILE_PATH, "rU") as configFile:
        config = json.loads(configFile.read())

        # If configuration file specifies optional values, replace the default with them.

        if "goesConfiguration" in config:
            if "dataChannel" in config["goesConfiguration"]:
                GOES_DATA_CHANNEL = config["goesConfiguration"]["dataChannel"]

        if "timeConfiguration" in config:
            if "centuryPrefix" in config["timeConfiguration"]:
                CENTURY_PREFIX = config["timeConfiguration"]["centuryPrefix"]

        os.system("getDcpMessages -u {} -P {} -h {} -p {} -f ./st.sc -x > {}".format(
            config["lrgsConnection"]["username"],
            config["lrgsConnection"]["password"],
            config["lrgsConnection"]["host"],
            config["lrgsConnection"]["port"],

            MESSAGE_FILE_PATH
        ))

        with open(MESSAGE_FILE_PATH, "rU") as message_file:
            # Remove any messages that are just spaces or blank lines.
            messages_iterable = filter(None, map(str.strip, message_file.read().strip().split("\n")))

            for cleaned_message in messages_iterable:
                message_headers = cleaned_message[:37]
                message_data = cleaned_message[37:]

                goes_id = message_headers[:8]
                goes_channel = int(message_headers[26:29])

                # Format: YYYYDDDHHMMSS. Convert it to ISO 8601 for the API.
                arrival_time_text = message_headers[8:19]
                arrival_time_object = datetime.datetime.strptime(CENTURY_PREFIX + arrival_time_text, "%Y%j%H%M%S")

                # We only want to process data from the data channel (GOES 19).
                if goes_channel == GOES_DATA_CHANNEL:
                    message = {
                        "goes_id": goes_id,
                        "arrival_time": arrival_time_object.isoformat(),
                        "failure_code": message_headers[19:20],
                        "signal_strength": int(message_headers[20:22]),
                        "frequency_offset": message_headers[22:24],
                        "modulation_index": message_headers[24:25],
                        "data_quality": message_headers[25:26],
                        "goes_channel": goes_channel,
                        "spacecraft": message_headers[29:30],
                        "data_source": message_headers[30:32],
                        "recorded_message_length": int(message_headers[32:37]),

                        "values": decode(message_data, 3,
                            len(config["goesStations"][goes_id]["sensors"]),
                            config["goesStations"][goes_id]["numReadings"]
                        ),

                        "message_text": cleaned_message
                    }

                    pp.pprint(message)

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
                            print("{}: The following message already has been saved: {}.".format(
                                datetime.datetime.now().isoformat(),
                                cleaned_message
                            ))
                            duplicate_exists = True

                    except requests.exceptions.Timeout:
                        print("{}: Time-out while checking for duplicate messages of: {}".format(
                            datetime.datetime.now().isoformat(),
                            cleaned_message
                        ))

                    except ValueError:
                        print("{}: An invalid JSON response was recieved.".format(datetime.datetime.now().isoformat()))

                    except requests.exceptions.RequestException as e:
                        # Catch any generic request errors.

                        print("{}: Error while checking for duplicate messages of: {}".format(
                            datetime.datetime.now().isoformat(),
                            cleaned_message
                        ))
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

                                print("{}: Automatic download of data failed.".format(
                                    datetime.datetime.now().isoformat()
                                ))
                                print(e)

                                sys.exit(1)
                else:
                    print("{}: Downloaded the following non-data message: {}".format(
                        datetime.datetime.now().isoformat(),
                        cleaned_message
                    ))

if __name__ == "__main__":
    main()
