#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#   Copyright 2016-2017 the Queen's University Biological Station

#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at

#       http://www.apache.org/licenses/LICENSE-2.0

#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import argparse
import datetime
import json
import math
import os
import pprint
import pytz
import requests
import sys
import time

from sudecode.sudecode import decode

CONFIG_FILE_PATH = "./config.json"
SEARCH_FILE_PATH = "./st.sc"
MESSAGE_FILE_PATH = "./latest-messages.txt"

GOES_DATA_CHANNEL = 19  # Default
CENTURY_PREFIX = "20"   # Default, hopefully this script won't be used in the 22nd century but just in case...

pp = pprint.PrettyPrinter(indent=2, compact=True)  # For nice log file output and debugging.


def main():
    global GOES_DATA_CHANNEL
    global CENTURY_PREFIX

    parser = argparse.ArgumentParser(description="Downloads climate data from QUBS satellite-linked climate stations.")
    parser.add_argument("--existing", action="store_true", help="Do not download new data and parse existing data.")
    args = parser.parse_args()

    with open(CONFIG_FILE_PATH, "rU") as configFile:
        config = json.loads(configFile.read())

        # If configuration file specifies optional values, replace the default with them.

        if "goesConfiguration" in config:
            if "dataChannel" in config["goesConfiguration"]:
                GOES_DATA_CHANNEL = config["goesConfiguration"]["dataChannel"]

        if "timeConfiguration" in config:
            if "centuryPrefix" in config["timeConfiguration"]:
                CENTURY_PREFIX = config["timeConfiguration"]["centuryPrefix"]

        # Run the LRGS command-line client software to fetch messages using search terms outlined in the .sc file.

        if not args.existing:
            os.system("getDcpMessages -a '---END---' -u {} -P {} -h {} -p {} -f {} -x > {}".format(
                config["lrgsConnection"]["username"],
                config["lrgsConnection"]["password"],
                config["lrgsConnection"]["host"],
                config["lrgsConnection"]["port"],

                SEARCH_FILE_PATH,
                MESSAGE_FILE_PATH
            ))

        with open(MESSAGE_FILE_PATH, "rU") as message_file:
            # Remove any messages that are just spaces or blank lines.
            messages_list = list(filter(None, map(str.strip, message_file.read().strip().split("---END---"))))

            # Set a lock to inform clients that the server is currently receiving data (and they may want to hold off
            # refreshing).
            requests.patch(
                "{api_url}/settings/receiving_data/".format(api_url=config["apiConnection"]["url"]),
                data={"value": "1"},
                auth=(
                    config["apiConnection"]["username"],
                    config["apiConnection"]["password"]
                )
            )

            # Loop through remaining messages and process each one. Reverse to go from earliest to latest.

            for cleaned_message in reversed(messages_list):
                # Split message into the headers and the actual data.

                try:
                    message_headers = cleaned_message[:37]
                    message_data = cleaned_message[37:]

                    goes_id = message_headers[:8]
                    goes_channel = int(message_headers[26:29])
                    # TODO: Check for message length transmission errors.

                    # Format: (YY)YYDDDHHMMSS. Convert it to ISO 8601 for the API.
                    arrival_time = CENTURY_PREFIX + message_headers[8:19]
                    arrival_time_object = datetime.datetime.strptime(arrival_time, "%Y%j%H%M%S").replace(
                        tzinfo=pytz.UTC
                    )
                    print(arrival_time_object.isoformat())

                    # We only want to process data from the data channel (GOES 19).
                    if goes_channel == GOES_DATA_CHANNEL:
                        # Create a dictionary representing the data payload for the POST request to the API.
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
                                             config["goesStations"][goes_id]["numSensors"],
                                             config["goesStations"][goes_id]["numReadings"]),

                            "message_text": cleaned_message,
                            "station": None
                        }

                        pp.pprint(message)

                        # Initialize an empty dictionary to hold station data sorted into sensor type.
                        station_sensor_data = {}
                        station_links_by_sensor_id = {}
                        station_id = -1

                        # Check for repeat messages.

                        duplicate_exists = False
                        metadata_fetch_failure = False

                        try:
                            # Request for messages from the same GOES ID with an arrival time plus or minus one second
                            # from the current message's arrival time...

                            r = requests.get(
                                "{api_url}/messages/".format(api_url=config["apiConnection"]["url"]),
                                params={
                                    "goes_id": message["goes_id"],
                                    "start": arrival_time_object - datetime.timedelta(seconds=1),
                                    "end": arrival_time_object + datetime.timedelta(seconds=1)
                                }
                            )

                            result = r.json()

                            # ... if one appears, it should be the same and thus the message should not be inserted
                            # again. A flag is set to prevent insertion.

                            if len(result) > 0:
                                print("{}: The following message already has been saved: {}.".format(
                                    datetime.datetime.now().isoformat(),
                                    cleaned_message
                                ))
                                duplicate_exists = True

                        except requests.exceptions.Timeout:
                            # A Timeout error occurred; this should be logged.
                            print("{}: Time-out while checking for duplicate messages of: {}".format(
                                datetime.datetime.now().isoformat(),
                                cleaned_message
                            ))

                        except ValueError:
                            # Decoding the JSON response failed; this should be logged.
                            print("{}: An invalid JSON response was recieved.".format(
                                datetime.datetime.now().isoformat())
                            )

                        except requests.exceptions.RequestException as e:
                            # Catch any generic request errors.

                            print("{}: Error while checking for duplicate messages of: {}".format(
                                datetime.datetime.now().isoformat(),
                                cleaned_message
                            ))
                            print(e)

                        try:
                            r = requests.get(
                                "{api_url}/stations/".format(api_url=config["apiConnection"]["url"]),
                                params={
                                    "goes_id": message["goes_id"]
                                }
                            )

                            station_data = r.json()
                            station_id = station_data[0]["id"]

                            # Update message object to include a correct station ID.
                            message["station"] = station_id

                            r = requests.get(
                                "{api_url}/stations/{station_id}/sensors/".format(
                                    api_url=config["apiConnection"]["url"],
                                    station_id=station_id
                                )
                            )

                            station_sensors = r.json()

                            for s in range(0, len(station_sensors)):
                                # TODO: Remove hardcoded 4 (readings per message).
                                o = s * 4
                                station_sensor_data[station_sensors[s]["id"]] = message["values"][o:o+4]

                            r = requests.get(
                                "{api_url}/stations/{station_id}/sensor-links/".format(
                                    api_url=config["apiConnection"]["url"],
                                    station_id=station_id
                                ),
                                params={"deep": True}
                            )

                            station_links = r.json()

                            for l in range(0, len(station_links)):
                                station_links_by_sensor_id[station_links[l]["sensor"]["id"]] = station_links[l]

                        except ValueError:
                            metadata_fetch_failure = True

                        except requests.exceptions.RequestException:
                            metadata_fetch_failure = True

                        # If a duplicate doesn't exist (i.e. the flag has not been set), post the message to the API.
                        if not (duplicate_exists or metadata_fetch_failure):
                            times_to_repeat = 1
                            cancel_next_repeat = False

                            while times_to_repeat > 0:
                                times_to_repeat -= 1

                                try:
                                    # Add message to database.

                                    r = requests.post(
                                        "{}/messages/".format(config["apiConnection"]["url"]),
                                        json=message,
                                        auth=(
                                            config["apiConnection"]["username"],
                                            config["apiConnection"]["password"]
                                        )
                                    )
                                    created_message = r.json()

                                    # Add readings to database.

                                    for sensor_id, sensor_values in station_sensor_data.items():
                                        for v in range(0, len(sensor_values)):
                                            # Calculate the closest quarter of an hour mark, where the last reading took
                                            # place. This assumes that all readings happen on the quarter of an hour.

                                            arrival_seconds = (
                                                arrival_time_object.minute * 60 +
                                                arrival_time_object.second +
                                                arrival_time_object.microsecond * 1e-6
                                            )
                                            delta = arrival_seconds - math.floor(arrival_seconds / 900.) * 900
                                            nearest_quarter = arrival_time_object - datetime.timedelta(seconds=delta)

                                            # Then, calculate the offset time from the reading index by multiplying the
                                            # time between readings by the index (since the order of values is most
                                            # recent to past).
                                            # TODO: The 15 shouldn't be hardcoded either, should be calculated from
                                            # config.
                                            reading_time = nearest_quarter - datetime.timedelta(minutes=15 * v)

                                            reading = {
                                                "read_time": reading_time.isoformat(),
                                                "value": sensor_values[v],
                                                "sensor": sensor_id,
                                                "station": station_id,
                                                "station_sensor_link": station_links_by_sensor_id[sensor_id]["id"],
                                                "message": created_message["id"]
                                            }

                                            # pp.pprint(reading)

                                            # Add reading to database.
                                            requests.post(  # r =
                                                "{}/readings/".format(config["apiConnection"]["url"]),
                                                json=reading,
                                                auth=(
                                                    config["apiConnection"]["username"],
                                                    config["apiConnection"]["password"]
                                                )
                                            )

                                except requests.exceptions.Timeout:
                                    # Try a single retry.

                                    if cancel_next_repeat:
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
                        # A message was retrieved that was not on the GOES data channel; log it and move on.
                        print("{}: Downloaded the following non-data message: {}".format(
                            datetime.datetime.now().isoformat(),
                            cleaned_message
                        ))

                except (ValueError, IndexError):
                    print("{}: Could not parse message: {}".format(
                        datetime.datetime.now().isoformat(),
                        cleaned_message
                    ))

            # Reset the lock to indicate that all data has been received from a batch.
            requests.patch(
                "{}/settings/receiving_data/".format(config["apiConnection"]["url"]),
                data={"value": "0"},
                auth=(
                    config["apiConnection"]["username"],
                    config["apiConnection"]["password"]
                )
            )

if __name__ == "__main__":
    main()
