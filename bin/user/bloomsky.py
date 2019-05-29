#!/usr/bin/python
"""
bloomsky.py

A WeeWX driver for the BloomSky family of personal weather devices.

Copyright (C) 2017-19 Gary Roderick                 gjroderick<at>gmail.com

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program.  If not, see http://www.gnu.org/licenses/.

Version: 0.1.1                                    Date: 29 May 2019

Revision History
    29 May 2019         v0.1.1
        - added missing barometer, luminance and raining fields to default
          sensor map
    25 June 2017        v0.1.0
        - initial release


To use this driver:

1.  Put this file in $BIN_ROOT/user.

2.  Add the following stanza to weewx.conf:

[Bloomsky]
    # This section is for the BloomSky station

    # BloomSky API key obtained from dashboard.bloomsky.com
    api_key = INSERT_API_KEY_HERE

    # BloomSky claim data is updated from the station every 5-8 minutes.
    # How often in seconds the driver will poll the BloomSky API. Default is
    # 60 seconds
    poll_interval = 60

    # Number of times to try to get a response from the BloomSky API before
    # aborting the attempt. Default is 3.
    max_tries = 3

    # Time to wait in seconds between retries. Default is 10 seconds.
    retry_wait = 10

    # The driver itself
    driver = user.bloomsky

3.  The BloomSky driver uses a default sensor map to map BloomSky API fields to
common WeeWX fields. If required this default sensor map can be overridden by
adding a [[sensor_map]] stanza to the [Bloomsky] stanza in weewx.conf. To
override the default sensor map add the following to the [Bloomsky]
stanza in weewx,conf altering/removing/adding WeeWX field names as required:

    # Define a mapping to map BloomSky API fields to WeeWX fields.
    #
    # Format is weewx_field = bloomsky_api_field
    #
    # where:
    #   weewx_field is a WeeWX field name to be included in the generated loop
    #       packet
    #   bloomsky_api_field is a BloomSky API JSON response field name
    #
    #   Note: WeeWX field names will be used to populate the generated loop
    #         packets. Fields will only be saved to database if the field name
    #         is included in the in-use database schema.
    #
    #   Child groups in the JSON response are designated by a [[[ ]]] stanza,
    #   eg [[[Data]]].
    #
    [[sensor_map]]
        deviceID = DeviceID
        deviceName = DeviceName
        [[[Data]]]
            outTemp = Temperature
            txBatteryStatus = Voltage
            UV = UVIndex
            outHumidity = Humidity
            barometer = Pressure
            imageURL = ImageURL
            deviceType = DeviceType
            night = Night
            raining = Rain
            luminance = Luminance
            imageTimestamp = ImageTS
        [[[Point]]]
            inTemp = Temperature
            inHumidity = Humidity
        [[[Storm]]]
            rainRate = RainRate
            windSpeed = SustainedWindSpeed
            windDir = WindDirection
            windGust = WindGust
            dailyRain = RainDaily

4.  Add the following stanza to weewx.conf:

    Note: If an [Accumulator] stanza already exists in weewx.conf just add the
          child settings.

[Accumulator]
    [[deviceID]]
        adder = noop
    [[deviceName]]
        adder = noop
    [[imageURL]]
        adder = noop
    [[deviceType]]
        adder = noop
    [[night]]
        adder = noop
    [[imageTimestamp]]
        adder = noop
    [[raining]]
        adder = noop

5.  In weewx.conf under [Station] set the station_type option as follows:

    station_type = Bloomsky

6.  Before running WeeWX with the BloomSky driver you may wish to run the driver
from the command line to ensure correct operation. To run the driver from the
command line enter one of the the following commands depending on your WeeWX
installation type:

    setup.py install:
    $ PYTHONPATH=/home/weewx/bin python /home/weewx/bin/user/bloomsky.py --run-driver --api-key=INSERT_API_KEY

    or

    any other install type:
    $ PYTHONPATH=/usr/share/weewx python /usr/share/weewx/user/bloomsky.py --run-driver --api-key=INSERT_API_KEY

    This should result in loop packets being displayed on the terminal windows
    every 60 seconds.

7.  If WeeWX is running stop then start WeeWX otherwise start WeeWX.
"""

# Python imports
import Queue
import json
import syslog
import threading
import time
import urllib2

from urllib import urlencode

# WeeWX imports
import weeutil

import weewx.drivers
import weewx.wxformulas

DRIVER_NAME = 'Bloomsky'
DRIVER_VERSION = "0.1.1"


def logmsg(level, msg):
    syslog.syslog(level, 'bloomsky: %s: %s' %
                  (threading.currentThread().getName(), msg))


def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)


def logdbg2(msg):
    if weewx.debug >= 2:
        logmsg(syslog.LOG_DEBUG, msg)


def logdbg3(msg):
    if weewx.debug >= 3:
        logmsg(syslog.LOG_DEBUG, msg)


def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)


def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)


def loader(config_dict, engine):
    return BloomskyDriver(**config_dict[DRIVER_NAME])


def confeditor_loader():
    return BloomskyConfEditor()


class BloomskyConfEditor(weewx.drivers.AbstractConfEditor):
    @property
    def default_stanza(self):
        return """
[Bloomsky]
    # This section is for the BloomSky station

    # BloomSky API key obtained from dashboard.bloomsky.com
    api_key = INSERT_API_KEY_HERE

    # The driver itself
    driver = user.bloomsky
"""

    def prompt_for_settings(self):
        settings = dict()
        print "Specify the API key from dashboard.bloomsky.com"
        settings['api_key'] = self._prompt('api_key')
        return settings


class BloomskyDriver(weewx.drivers.AbstractDevice):
    """BloomSky driver class."""

    # map from BloomSky API field names to WeeWX db schema names
    DEFAULT_SENSOR_MAP = {'deviceID':   'DeviceID',
                          'deviceName': 'DeviceName',
                          'Data':       {'outTemp':         'Temperature',
                                         'txBatteryStatus': 'Voltage',
                                         'UV':              'UVIndex',
                                         'outHumidity':     'Humidity',
                                         'imageURL':        'ImageURL',
                                         'deviceType':      'DeviceType',
                                         'barometer':       'Pressure',
                                         'luminance':       'Luminance',
                                         'raining':         'Rain',
                                         'night':           'Night',
                                         'imageTimestamp':  'ImageTS'},
                          'Point':      {'inTemp':          'Temperature',
                                         'inHumidity':      'Humidity'},
                          'Storm':      {'rainRate':        'RainRate',
                                         'windSpeed':       'SustainedWindSpeed',
                                         'windDir':         'WindDirection',
                                         'windGust':        'WindGust',
                                         'rainDaily':       'RainDaily'}
                          }

    def __init__(self, **stn_dict):
        loginf('driver version is %s' % DRIVER_VERSION)
        self.sensor_map = dict(BloomskyDriver.DEFAULT_SENSOR_MAP)
        if 'sensor_map' in stn_dict:
            self.sensor_map.update(stn_dict['sensor_map'])
        loginf('sensor map is %s' % self.sensor_map)
        # number of time to try and get a response from the BloomSky API
        max_tries = int(stn_dict.get('max_tries', 3))
        # wait time in seconds between retries
        retry_wait = int(stn_dict.get('retry_wait', 10))
        # BloomSky claim data is updated from the station every 5-8 minutes.
        # Set how often (in seconds) we should poll the API.
        poll_interval = int(stn_dict.get('poll_interval', 120))
        # API key issued obtained from dashboard.bloomsky.com
        api_key = stn_dict['api_key']
        obfuscated = ''.join(('"....', api_key[-4:], '"'))
        logdbg('poll interval is %d seconds, API key is %s' % (poll_interval,
                                                               obfuscated))
        logdbg('max tries is %d, retry wait time is %d seconds' % (max_tries,
                                                                   retry_wait))
        self.last_rain = None
        # create an ApiClient object to interact with the BloomSky API
        self.collector = ApiClient(api_key,
                                   poll_interval=poll_interval,
                                   max_tries=max_tries,
                                   retry_wait=retry_wait)
        # the ApiClient runs in its own thread so start the thread
        self.collector.startup()

    def closePort(self):
        """Shutdown the ApiClient object thread.

        Override the base class closePort() method. We don't have a port to
        close but rather we shut down the ApiClient object thread.
        """
        self.collector.shutdown()

    @property
    def hardware_name(self):
        return DRIVER_NAME

    def genLoopPackets(self):
        """Wait for BloomSky API from the ApiClient and yield a loop packets.

        Run a continuous loop checking the ApiClient queue for data. When data
        arrives map the raw data to a WeeWX loop packet and yield the packet.
        """

        while True:
            # wrap in a try to catch any instances where the queue is empty
            try:
                # get any day from the collector queue
                raw_data = self.collector.queue.get(True, 10)
                # create a loop packet
                packet = self.data_to_packet(raw_data)
                # log the packet but only if debug>=2
                logdbg2('Packet: %s' % packet)
                # if we did get a packet then yield it for processing
                if packet:
                    yield packet
            except Queue.Empty:
                # there was nothing in the queue so continue
                pass

    def data_to_packet(self, data):
        """Convert BloomSky data to WeeWX packet format.

        The Collector provides BloomSky API response in the form of a dict that
        may contain nested dicts of data. Fist map the BloomSky data to a flat
        WeeWX data packet then add a packet timestamp and unit system fields.
        Finally calculate rain since last packet.

        Input:
            data: BloomSky API response in dict format

        Returns:
            A WeeWX loop packet
        """

        # map the BloomSky API data to a WeeWX loop packet
        packet = self._map_fields(data, self.sensor_map)
        # add dateTime and usUnits fields
        packet['dateTime'] = int(time.time() + 0.5)
        # we ask the BloomSky API data for international units which gives us
        # data conforming to the METRICWX unit system
        packet['usUnits'] = weewx.METRICWX
        # BloomSky reports 2 rainfall fields, RainDaily and 24hRain; the
        # rainfall since midnight and the rainfall in the last 24 hours
        # respectively. Therefore we need to calculate the incremental rain
        # since the last packet using the RainDaily field (which was translated
        # to the WeeWX dailyRain field). We will see a decrement at midnight
        # when the counter is reset, this may cause issues if it is raining at
        # the time but there is little that can be done.
        if 'rainDaily' in packet:
            # get the rain so far today
            total = packet['rainDaily']
            # have we seen a daily rain reset?
            if (total is not None and self.last_rain is not None
                    and total < self.last_rain):
                # yes we have, just log it
                loginf("dailyRain decrement ignored:"
                       " new: %s old: %s" % (total, self.last_rain))
            # calculate the rainfall since the last packet
            packet['rain'] = weewx.wxformulas.calculate_rain(total,
                                                             self.last_rain)
            # adjust our last rain total
            self.last_rain = total
        return packet

    @staticmethod
    def _map_fields(data, map):
        """Map BloomSky API response fields to WeeWX loop packet fields.

        Iterate over all all sensor map entries and if a field exists that
        matches the map entry then map the field to a packet dict. Some data
        fields may be a nested dict so recursively call the _map_fields()
        method to map any child data fields.

        Input:
            data: BloomSky API response in dict format
            map: The sensor map (dict)

        Returns:
            A WeeWX loop packet consisting of only those fields in the sensor
            map that also exist in the source data dict.
        """

        # initialise our result
        packet = dict()
        # step through each key:value pair in the sensor map
        for (w_field, b_field) in map.iteritems():
            # If the 'value' element is a dict we have a sub-map. Call
            # ourselves using the sub-data and sub-map.
            if hasattr(b_field, 'keys'):
                # we have a sub-map
                packet.update(BloomskyDriver._map_fields(data.get(w_field, {}),
                                                         b_field))
            else:
                # no-sub map so map to our result if we have data
                if b_field in data:
                    packet[w_field] = data[b_field]
        return packet


class Collector(object):
    """Base class for the client that polls an API."""

    queue = Queue.Queue()

    def startup(self):
        pass

    def shutdown(self):
        pass


class ApiClient(Collector):
    """Class to poll the BloomSky API and return data to the driver."""

    # endpoint for the BloomSky API GET request
    API_URL = 'https://api.bloomsky.com/api/skydata/'

    # Data fields contained in the base API response
    BASE_ITEMS = ['DeviceID', 'LAT', 'LON', 'ALT', 'UTC', 'DST', 'Searchable',
                  'RegisterTime', 'CityName', 'StreetName', 'FullAddress',
                  'DeviceName', 'BoundedPoint', 'NumOfFollowers', 'VideoList',
                  'VideoList_C', 'NumOfFavorites', 'PreviewImageList'
                  ]
    # Data fields contained in the API response 'Data' child field
    DATA_ITEMS = ['ImageURL', 'ImageTS', 'Pressure', 'Luminance',
                  'Temperature', 'Night', 'Voltage', 'UVIndex', 'TS', 'Rain',
                  'Humidity', 'DeviceType'
                  ]
    # Data fields contained in the API response 'Point' child field
    POINT_ITEMS = ['Temperature', 'Humidity']
    # Data fields contained in the API response 'Storm' child field
    STORM_ITEMS = ['RainRate', 'SustainedWindSpeed', 'RainDaily',
                   'WindDirection', 'WindGust'
                   ]
    # map for wind direction, API provides a 16-wind compass point rather than
    # numeric degrees
    WIND_DIR_MAP = {"N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
                    "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
                    "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
                    "W": 270, "WNW": 292.5, "NW": 315, "NWN": 337.5
                    }
    # Some API response fields require some form of manipulation/translation
    # before handing to the driver proper. This dict maps to the API response
    # fields that require manipulation/translation to a method in the class.
    # Nested dictionaries are used for fields in child fields.
    TRANSLATIONS = {'Data': {'Voltage': '_trans_voltage',
                             'UVIndex': '_trans_uv',
                             'Luminance': '_trans_luminance'
                             },
                    'Storm': {'WindDirection': '_trans_wind_dir'}
                    }

    def __init__(self, api_key, poll_interval=60, max_tries=3, retry_wait=10):
        """Initialise our class."""

        # the API key from dashboard.bloomsky.com
        self._api_key = api_key
        # interval between polls of the API, default is 120 seconds
        self._poll_interval = poll_interval
        # how many times to poll the API before giving up, default is 3
        self._max_tries = max_tries
        # period in seconds to wait before polling again, default is 10 seconds
        self._retry_wait = retry_wait
        # get a station data object to do the handle the interaction with the
        # BloomSky API
        self.sd = ApiClient.StationData(api_key)
        self._thread = None
        self._collect_data = False

    def collect_data(self):
        """Loop forever waking periodically to see if it is time to quit."""

        # ts of last time API was polled
        last_poll = 0
        # collect data continuously while we are told to collect data
        while self._collect_data:
            now = int(time.time())
            # is it time to poll?
            if now - last_poll > self._poll_interval:
                # yes, poll a max of self._max_tries times
                for tries in range(self._max_tries):
                    # wrap oin a try..except so we can catch any errors
                    try:
                        # get the raw JSON API response
                        raw_data = self.sd.get_data()
                        # extract the data we want from the JSON response, do
                        # any manipulation/translation and return as a dict
                        data = ApiClient.extract_data(raw_data)
                        # log the extracted data for debug purposes
                        logdbg3("Extracted data: %s" % data)
                        # put the data in the queue
                        Collector.queue.put(data)
                        # we are done so break out of the for loop
                        break
                    except (urllib2.HTTPError, urllib2.URLError), e:
                        # handle any errors caught
                        logerr("Failed attempt %s of %s to get data: %s" %
                               (tries + 1, self._max_tries, e))
                        logdbg("Waiting %s seconds before retry" %
                               self._retry_wait)
                        time.sleep(self._retry_wait)
                else:
                    # if we did not get any data after self._max_tries log it
                    logerr("Failed to get data after %d attempts" %
                           self._max_tries)
                # reset the last poll ts
                last_poll = now
                logdbg('Next update in %s seconds' % self._poll_interval)
            # sleep and see if its time to poll again
            time.sleep(1)

    @staticmethod
    def extract_data(data):
        """Extract the data of interest.

        Iterate through each API response field we are interested in and if it
        exists copy the data from the JSON response to a dict. Once complete,
        perform any manipulation/translation of any of the data fields
        (ie removing entries for non-existent sensors) then return the
        resulting dict.

        Input:
            data: JSON object containing the API response

        Returns:
            A dict containing the extracted and translated data. Dict may
            contain nested dicts.
        """

        data_dict = dict()
        for item in ApiClient.BASE_ITEMS:
            if item in data[0]:
                data_dict[item] = data[0][item]
        if 'Data' in data[0]:
            data_dict['Data'] = dict()
            for item in ApiClient.DATA_ITEMS:
                if item in data[0]['Data']:
                    data_dict['Data'][item] = data[0]['Data'][item]
        if 'Point' in data[0]:
            data_dict['Point'] = dict()
            for item in ApiClient.POINT_ITEMS:
                if item in data[0]['Point']:
                    data_dict['Point'][item] = data[0]['Point'][item]
        if 'Storm' in data[0]:
            data_dict['Storm'] = dict()
            for item in ApiClient.STORM_ITEMS:
                if item in data[0]['Storm']:
                    data_dict['Storm'][item] = data[0]['Storm'][item]
        # perform any manipulation/translation of the API response data (eg if
        # no Storm device UV will be 9999, WeeWX expects so UV field or data is
        # no sensor so delete the UV entry)
        data_dict.update(ApiClient.translate_data(data_dict,
                                                  ApiClient.TRANSLATIONS))
        return data_dict

    @staticmethod
    def translate_data(data, td):
        """Translate BloomSky API response data to meet WeeWX requirements."""

        # iterate over each item in the translation dict
        for key, value in td.iteritems():
            # if the item is dict then recursively call ourself to translate
            # any fields in the child dict
            if hasattr(value, 'keys'):
                if key in data:
                    data.update(ApiClient.translate_data(data[key], value))
            elif key in data:
                # The key is not a dict and the value contains the method we
                # must call for the translation. Obtain an object pointing to
                # the method required and call it.
                getattr(ApiClient, value)(data, key)
        return data

    @staticmethod
    def _trans_voltage(data, key):
        """Translate BloomSky API Voltage field.

        API provides voltage in mV, WeeWX uses V.

        Inputs:
            data: Dict containing the translated API response
            key:  Key to the dict of the field concerned
        """

        # wrap in a try..except in case the field contains non-numeric data
        try:
            # convert from mV to V
            data[key] = data[key]/1000.0
        except TypeError:
            # if the field contains non-numeric data we can't convert it so set
            # it to None
            data[key] = None

    @staticmethod
    def _trans_uv(data, key, not_present=9999):
        """Translate BloomSky API UVIndex field.

        API provides UV of 9999 is no UV (Storm) sensor exists, WeeWX expects
        there to be no UV field if no UV sensor exists.

        Inputs:
            data: Dict containing the translated API reponse
            key:  Key to the dict of the field concerned
            not_present: API response field 'UVField' value if no Storm is
                         present, default is 9999
        """

        # if the UV field is 9999, there is no Storm and no UV sensor so delete
        # the entry
        if data[key] == not_present:
            data.pop(key)

    @staticmethod
    def _trans_luminance(data, key, not_present=9999):
        """Translate BloomSky API Luminance field.

        API provides Luminance of 9999 is no Luminance (Storm) sensor exists,
        WeeWX expects there to be no Luminance field if no Luminance sensor
        exists.

        Inputs:
            data: Dict containing the translated API reponse
            key:  Key to the dict of the field concerned
            not_present: API response field 'Luminance' value if no Storm is
                         present, default is 9999
        """

        # if the Luminance field is 9999, there is no Storm and no Luminance
        # sensor so delete the entry
        if data[key] == not_present:
            data.pop(key)

    @staticmethod
    def _trans_wind_dir(data, key):
        """Translate BloomSky API WindDirection field.

        API provides WindDirection using one of the 16-wind compass points,
        WeeWX uses numeric degrees.

        Inputs:
            dir: String containing one of the 16-wind compass points
        """

        # lookup the direction in WIND_DIR_MAP using a default of None
        data[key] = ApiClient.WIND_DIR_MAP.get(data[key], None)

    def startup(self):
        """Start a thread that collects data from the BloomSky API."""

        self._thread = ApiClient.CollectorThread(self)
        self._collect_data = True
        self._thread.start()

    def shutdown(self):
        """Tell the thread to stop, then wait for it to finish."""

        if self._thread:
            self._collect_data = False
            self._thread.join()
            self._thread = None

    class CollectorThread(threading.Thread):
        """Class used to do BloomSky API calls in a thread."""

        def __init__(self, client):
            threading.Thread.__init__(self)
            self.client = client
            self.name = 'bloomsky-client'

        def run(self):
            # rather than letting the thread silently fail if an exception
            # occurs within the thread wrap in a try..except so the exception
            # can be caught and available exception information displayed
            try:
                # kick the collection off
                self.client.collect_data()
            except:
                # we have an exception so log what we can
                loginf('Exception:')
                weeutil.weeutil.log_traceback("    ****  ", syslog.LOG_INFO)

    class StationData(object):
        """Class to obtain station data from the BloomSky API."""

        def __init__(self, api_key):
            self._api_key = api_key
            self._last_update = 0

        def get_data(self, units='intl'):
            """Get raw data the BloomSky API."""

            # we pass the API key in the header
            headers = {'Authorization': self._api_key}
            # do we need to ask for international units, only if units=='intl'
            params = {}
            if units == 'intl':
                params['unit'] = units
            # make the request and get the returned data
            resp_json = ApiClient.get_request(ApiClient.API_URL,
                                              params, headers)
            self._last_update = int(time.time())
            return resp_json

    @staticmethod
    def get_request(url, params, headers):
        """Submit HTTP GET request and return any data as JSON object."""

        # encode the GET parameters
        data = urlencode(params)
        obfuscated = dict(headers)
        if 'Authorization' in obfuscated:
            obfuscated['Authorization'] = ''.join(("....", obfuscated['Authorization'][-4:]))
        logdbg("url: %s data: %s hdr: %s" % (url, params, obfuscated))
        # A urllib2.Request that includes a 'data' parameter value will be sent
        # as a POST request. the BloomSky API requires a GET request. So to
        # send as a GET request with data just append '?' and the 'data' to the
        # URL then create the request with just url and headers parameters.
        _url = ''.join((url, '?', data))
        # create a Request object
        req = urllib2.Request(url=_url, headers=headers)
        # submit the request
        resp = urllib2.urlopen(req).read()
        # convert the response to a JSON object
        resp_json = json.loads(resp)
        logdbg3("JSON API response: %s" % json.dumps(resp_json))
        # return the JSON object
        return resp_json


# To test this driver, do one of the following depending on your WeeWX install
# type:
#   PYTHONPATH=/home/weewx/bin python /home/weewx/bin/user/bloomsky.py
#
#   or
#
#   PYTHONPATH=/usr/share/weewx python /usr/share/weewx/user/bloomsky.py

if __name__ == "__main__":
    usage = """%prog [options] [--help]"""

    def main():
        import optparse
        syslog.openlog('wee_bloomsky', syslog.LOG_PID | syslog.LOG_CONS)
        parser = optparse.OptionParser(usage=usage)
        parser.add_option('--version', dest='version', action='store_true',
                          help='display BloomSky driver version number')
        parser.add_option('--debug', dest='debug', action='store_true',
                          help='display diagnostic information while running')
        parser.add_option('--run-driver', dest='run_driver', action='store_true',
                          metavar='RUN_DRIVER', help='run the BloomSky driver')
        parser.add_option('--api-key', dest='api_key', metavar='API_KEY',
                          help='BloomSky API key')
        parser.add_option('--get-json-data', dest='jdata', action='store_true',
                          help='get BloomSky API json response')
        (opts, args) = parser.parse_args()

        # if --debug raise our log level
        if opts.debug:
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

        # display driver version number
        if opts.version:
            print "%s driver version: %s" % (DRIVER_NAME, DRIVER_VERSION)
            exit(0)

        # run the driver
        if opts.run_driver:
            run_driver(opts.api_key)

        # get BloomSky API JSON response
        if opts.jdata:
            get_json_data(opts.api_key)

    def run_driver(api_key):
        """Run the BloomSky driver."""

        import weeutil.weeutil

        driver = None
        # wrap in a try..except so we can pickup a keyboard interrupt
        try:
            # get a BloomskyDriver object
            driver = BloomskyDriver(api_key=api_key)
            # continuously get loop packets and print them to screen
            for pkt in driver.genLoopPackets():
                print weeutil.weeutil.timestamp_to_string(pkt['dateTime']), pkt
        except KeyboardInterrupt:
            # we have a keyboard interrupt so shut down
            driver.closePort()

    def get_json_data(api_key):
        """Get the BloomSky API JSON format response and display on screen."""

        # get an ApiClient object
        api_client = ApiClient(api_key=api_key)
        # get the JSON response
        raw_data = api_client.sd.get_data()
        # display the JSON response on screen
        print json.dumps(raw_data, sort_keys=True, indent=2)

    main()
