# QUBS Climate Data Auto-Downloader

The QUBS climate network uses GOES satellites. This auto-downloader connects to the NOAA's DCS API using the LRGS Client
from [Cove Software](http://www.covesw.com/).

## Installation

1. Install software...
2. Install dependencies...
3. Add LrgsClient binaries to path...

## Configuration

The configuration file, `config.json`, stores a JSON object with the following configuration sub-objects.

### `apiConnection`

This object contains information on connecting to the API server.

`url`: The URL of the API server.

`username`: The username to connect to the API server with.

`password`: The password to connect to the API server with.

### `lrgsConnection`

This object contains information on connecting to the LRGS server.

`host`: The host of the LRGS server. Defaults to `"cdadata.wcda.noaa.gov"`.

`port`: The port of the LRGS server. Defaults to `16003`.

`username`: The username to connect to the LRGS server with.

`password`: The password to connect to the LRGS server with.

### `goesConfiguration`

This object contains information about the GOES data satellite used.

`dataChannel`: The data channel on which data messages are recieved.

### `timeConfiguration`

This object contains information about handling times.

`centuryPrefix`: The first two digits of the current year.

### `goesStations`

This object contains information on GOES climate stations. The key of the object
is the GOES ID of the station.

Within a station object:

`name`: The station name.

`numReadings`: The number of readings the station takes per hour.

`numSensors`: The number of sensors (not including battery information).

`battery`: Whether or not battery information is appended onto the message.

## Usage

TODO

### Making It Automatic

TODO
