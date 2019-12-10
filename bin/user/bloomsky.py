#!/usr/bin/env python
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

Version: 1.0.1                                    Date: 28 November 2019

Revision History
    28 November 2019    v1.0.1
        - revised sensor mapping now support multiple device IDs
        - additional exception handling to handle a malformed API response
        - fixed python shebang
    31 May 2019         v1.0.0
        - code now python 2.6+, 3.5+ (but not WeeWX 4) compatible
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
override the default sensor map add the following under the [Bloomsky]
stanza in weewx.conf altering/removing/adding WeeWX field maps as required:

    # Define a mapping to map BloomSky API fields to WeeWX fields.
    #
    # Format is weewx_field = device_id.field.element
    #
    # where:
    #   weewx_field is a WeeWX field name to be included in the generated loop
    #       packet
    #   device_id is a BloomSky device ID or glob pattern used to match a device
    #       ID. For example 12345678 would match the device ID 12345678, *1234
    #       would match the first device ID found that ends in 1234 and * would
    #       match the first device ID found.
    #   field is an optional entry used to access API response elements within 
    #       the Data, Point and Storm elements. For example, *.Data.Temperature 
    #       would return the Temperature element within the Data element of the 
    #       first device ID found, *.deviceName would return the deveiceName 
    #       element of the first device ID found.
    #   element is name of the desired BloomSky API response element. For 
    #       example, *.Storm.rainRate would access the rainRate element of the 
    #       Storm on the first device ID found.
    #
    #   Note: WeeWX field names will be used to populate the generated loop
    #         packets. Fields will only be saved to database if the field name
    #         is included in the in-use database schema.
    #
    [[sensor_map]]
        deviceID = *.DeviceID
        deviceName = *.DeviceName
        outTemp = *.Data.Temperature
        txBatteryStatus = *.Data.Voltage
        UV = *.Data.UVIndex
        outHumidity = *.Data.Humidity
        imageURL = *.Data.ImageURL
        deviceType = *.Data.DeviceType
        night = *.Data.Night
        imageTimestamp = *.Data.ImageTS
        luminance = *.Data.Luminance
        barometer = *.Data.pressure
        inTemp = *.Point.Temperature
        inHumidity = *.Point.Humidity
        rainRate = *.Storm.RainRate
        windSpeed = *.Storm.SustainedWindSpeed
        windDir = *.Storm.WindDirection
        windGust = *.Storm.WindGust
        rainDaily = *.Storm.RainDaily
        raining = *.Data.raining

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


7.  If WeeWX is running stop then start WeeWX otherwise start WeeWX.
"""

# Python imports
import fnmatch
import json
import socket
import syslog
import threading
import time

# python 2/3 compatibility shims
from six.moves import queue
from six.moves import urllib

# WeeWX imports
import weecfg

import weeutil.weeutil
import weewx.drivers
import weewx.wxformulas

DRIVER_NAME = 'Bloomsky'
DRIVER_VERSION = "1.0.1"


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


# ============================================================================
#                         class BloomskyConfEditor
# ============================================================================


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
        print("Specify the API key from dashboard.bloomsky.com")
        settings['api_key'] = self._prompt('api_key')
        return settings


# ============================================================================
#                           class BloomskyDriver
# ============================================================================


class BloomskyDriver(weewx.drivers.AbstractDevice):
    """BloomSky driver class."""

    # Sane default map from Bloomsky API field names to weeWX db schema names
    # that will work in most cases (ie single Sky and/or Storm). Accounts with
    # multiple DeviceIDs (ie more than one Sky or more than one Storm) will
    # need to define a map in weewx.conf.
    DEFAULT_SENSOR_MAP = {'deviceID':        '*.DeviceID',
                          'deviceName':      '*.DeviceName',
                          'outTemp':         '*.Data.Temperature',
                          'txBatteryStatus': '*.Data.Voltage',
                          'UV':              '*.Data.UVIndex',
                          'outHumidity':     '*.Data.Humidity',
                          'imageURL':        '*.Data.ImageURL',
                          'deviceType':      '*.Data.DeviceType',
                          'night':           '*.Data.Night',
                          'imageTimestamp':  '*.Data.ImageTS',
                          'luminance':       '*.Data.Luminance',
                          'barometer':       '*.Data.pressure',
                          'inTemp':          '*.Point.Temperature',
                          'inHumidity':      '*.Point.Humidity',
                          'rainRate':        '*.Storm.RainRate',
                          'windSpeed':       '*.Storm.SustainedWindSpeed',
                          'windDir':         '*.Storm.WindDirection',
                          'windGust':        '*.Storm.WindGust',
                          'rainDaily':       '*.Storm.RainDaily',
                          'raining':         '*.Data.raining'
                          }
    DEFAULT_DELTAS = {'rain': 'rainDaily'}

    def __init__(self, **stn_dict):

        loginf('driver version is %s' % DRIVER_VERSION)
        self.sensor_map = dict(BloomskyDriver.DEFAULT_SENSOR_MAP)
        if 'sensor_map' in stn_dict:
            self.sensor_map.update(stn_dict['sensor_map'])
        loginf('sensor map is %s' % self.sensor_map)

        # get the deltas
        self.deltas = stn_dict.get('deltas', BloomskyDriver.DEFAULT_DELTAS)
        loginf('deltas is %s' % self.deltas)

        # number of time to try and get a response from the Bloomsky API
        max_tries = int(stn_dict.get('max_tries', 3))
        # wait time in seconds between retries
        retry_wait = int(stn_dict.get('retry_wait', 10))
        # BloomSky claim data is updated from the station every 5-8 minutes.
        # Set how often (in seconds) we should poll the API.
        poll_interval = int(stn_dict.get('poll_interval', 60))
        # API key issued obtained from dashboard.bloomsky.com
        api_key = stn_dict['api_key']
        obfuscated = ''.join(('"....', api_key[-4:], '"'))
        logdbg('poll interval is %d seconds, API key is %s' % (poll_interval,
                                                               obfuscated))
        logdbg('max tries is %d, retry wait time is %d seconds' % (max_tries,
                                                                   retry_wait))
        self._counter_values = dict()
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

    @property
    def ids(self):
        """Return the Bloomsky device IDs."""

        raw_data = None
        # loop until we get some raw data
        while raw_data is None:
            # wrap in try..except so we can catch the empty queue error
            try:
                # get any data from the collector queue
                raw_data = self.collector.queue.get(True, 10)
            except queue.Empty:
                # there was nothing in the queue so continue
                pass
        # The raw data will be a list of dicts where each dict is the data for
        # a particular device ID. Each dict should have a DeviceID field
        # containing the device ID.
        # initialise our response
        ids = []
        # iterate over each of the device dicts
        for device in raw_data:
            # append the device ID to our response, be prepared to catch the
            # case where there is no DeviceID field
            try:
                ids.append(device['DeviceID'])
            except KeyError:
                pass
        return ids

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
                # create a loop packet and initialise with dateTime and usUnits
                packet = {'dateTime': int(time.time() + 0.5),
                          'usUnits': weewx.METRICWX
                          }
                self.map_to_fields(packet, raw_data)
                # if we did get a packet then yield it for processing
                if packet:
                    self.calculate_rain(packet)
                    # log the packet but only if debug>=2
                    logdbg2('Packet: %s' % packet)
                    yield packet
            except queue.Empty:
                # there was nothing in the queue so continue
                pass

    def calculate_rain(self, packet):
        """Calculate rainfall values for rain fields."""

        for delta_field, src_field in self.deltas.iteritems():
            if src_field in packet:
                packet[delta_field] = self._calc_rain(packet[src_field],
                                                      self._counter_values.get(src_field))
                self._counter_values[src_field] = packet[src_field]

    @staticmethod
    def _calc_rain(new_total, old_total):
        """Calculate rainfall given the current and previous totals."""

        delta = None
        if new_total is not None and old_total is not None:
            if new_total >= old_total:
                delta = new_total - old_total
            else:
                delta = new_total
        return delta

    def map_to_fields(self, packet, raw_data):
        """Map Bloomsky raw data to weeWX packet fields.

        The Collector provides BloomSky API response in the form of a dict that
        may contain nested dicts of data. Fist map the BloomSky data to a flat
        WeeWX data packet then add a packet timestamp and unit system fields.
        Finally calculate rain since last packet.
        Bloomsky API response is provided as a list of dicts with one dict per
        device ID. Iterate over each sensor map entry adding sensor data to the
        packet.

        Input:
            data: BloomSky API response in dict format
        Inputs:
            packet: the packet to be yielded
            data:   Bloomsky API response in list of dict format
        """

        # iterate over each of the sensors in the sensor map
        for s in self.sensor_map:
            # obtain the mapped sensor value from the raw data, if it can't be
            # found the returned value will be None
            value = self.get_sensor_value(raw_data, self.sensor_map[s])
            # if we have a value other than None add the field to the packet
            if value is not None:
                packet[s] = value
        return

    @staticmethod
    def get_sensor_value(data, sensor_pattern):
        """Get a Bloomsky sensor value given a Bloomsky sensor mapping.

        Bloomsky API response is returned as a list of dicts with each dict
        representing a single device ID. To find a data element represented
        by a sensor mapping we first iterate over the dicts (device IDs) until
        we find a matching device and then traverse the device's data (which
        will contain nested dicts) to find the particular element.

        Sensor map is in the format:

            [XXXXX.][YYYYY.]ZZZZZ

        where:
            - XXXXX is an optional device ID value or glob pattern to be used
              to match a device ID. Use of * will match the first available
              device ID.
            - YYYYY is an optional value or pattern to match nested data in the
              API response. If used will normally be 'Data', 'Point' or
              'Storm'.
            - ZZZZZ is a Bloomsky API JSON response field name or glob pattern
              to be used to match a field.

        Inputs:
            data:           list of dicts containing the Bloomsky data
            sensor_pattern: sensor map pattern being used

        Returns:
            The data element referred to by the sensor map pattern. Will be
            None if no element found.
        """

        # initialise our response, assume nothing found to start with
        element = None
        # Need the device ID portion of the sensor pattern so we know when we
        # have a matching device ID. Split the sensor pattern into device ID
        # portion and the rest.
        parts = sensor_pattern.split('.', 1)
        # iterate over each device ID dict in our data
        for device in data:
            # do we have a device ID specifier or just a field specifier
            if len(parts) > 1:
                if BloomskyDriver._match(device['DeviceID'], parts[0]):
                    element = BloomskyDriver._find_in_device(device, parts[1])
                    if element:
                        return element
            else:
                # The sensor pattern is for a field only, that makes it simple,
                # just look for the field at the top level of the dict.
                # Iterate over the top level items in the dict looking for a
                # matching field. If the match happens to be a dict then ignore
                # it as our sensor pattern does not support that.
                for (k, v) in device.iteritems():
                    if sensor_pattern == k and not hasattr(k, 'keys'):
                        element = v
        return element

    @staticmethod
    def _find_in_device(data, sensor_pattern):
        """Find a data element for a device ID given a partial sensor map.

        Recursively search the data dict for a key that matches the sensor
        pattern.

        Inputs:
            data:           device ID data to be searched
            sensor_pattern: sensor map pattern being used

        Returns:
            The data element referred to by the sensor map pattern. Will be
            None if no element found.
        """

        # start of assuming we have no match
        element = None
        # Split the sensor map at the first period '.' character. Look for a
        # match for the first part of the pattern and then iteratively look for
        # the rest as required until the data element being sought is found (if
        # it exists)
        parts = sensor_pattern.split('.', 1)
        # do we have a 'dotted' sensor map or just a sensor/field name
        if len(parts) > 1:
            # it's a 'dotted' sensor map
            for (k, v) in data.iteritems():
                # iterate over the key, value pairs of our data to see if we
                # have a match
                if BloomskyDriver._match(k, parts[0]):
                    # we have a match so recursively call ourself to continue
                    # the search at the next 'level' down
                    element = BloomskyDriver._find_in_device(v, parts[1])
        else:
            # just a straight up field/sensor name
            for (k, v) in data.iteritems():
                # iterate over the key, value pairs of our data to see if we
                # have the field we want
                if sensor_pattern == k:
                    # we have a match so save it so we can return it
                    element = v
        return element

    @staticmethod
    def _match(value, pattern):
        """Check if a value matches a glob pattern.

        Returns True if value glob matches pattern otherwise returns False.

        Inputs:
            pattern: the glob pattern to be used to check against
            value:   the value being checked

        Returns
            Boolean indicating whether there is a match or not
        """

        matches = fnmatch.filter([value], pattern)
        return True if matches else False


# ============================================================================
#                              class Collector
# ============================================================================


class Collector(object):
    """Base class for a client that polls an API."""

    queue = queue.Queue()

    def startup(self):
        pass

    def shutdown(self):
        pass


# ============================================================================
#                              class ApiClient
# ============================================================================


class ApiClient(Collector):
    """Class to poll the BloomSky API and return data to the driver."""

    # endpoint for the BloomSky API GET request
    """Poll the bloomsky API for data and put the data in the queue."""

    # endpoint for the Bloomsky API GET request
    API_URL = 'https://api.bloomsky.com/api/skydata/'

    # Data fields contained in the base API response
    BASE_ITEMS = ['LAT', 'LON', 'ALT', 'UTC', 'DST', 'Searchable', 'DeviceID',
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
        # interval between polls of the API, default is 60 seconds
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
                    # wrap in a try..except so we can catch any errors
                    try:
                        # get the raw JSON API response
                        raw_data = self.sd.get_data()
                        # extract the data we want from the JSON response, do
                        # any manipulation/translation and return as a list of
                        # dicts
                        data = ApiClient.extract_data(raw_data)
                        # log the extracted data for debug purposes
                        logdbg3("Extracted data: %s" % data)
                        # put the data in the queue
                        Collector.queue.put(data)
                        # we are done so break out of the for loop
                        break
                    except (urllib.error.HTTPError, urllib.error.URLError) as e:
                        # handle any errors caught
                        logerr("Failed attempt %s of %s to get data: %s" %
                               (tries + 1, self._max_tries, e))
                        logdbg("Waiting %s seconds before retry" %
                               self._retry_wait)
                        time.sleep(self._retry_wait)
                    except IndexError as e:
                        # most likely we got back a blank response or maybe
                        # something couldn't be found where it was expected
                        logerr("Invalid data received on attempt %s of %s: %s" %
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

        device_list = []
        for dev_id in data:
            device_dict = dict()
            for item in ApiClient.BASE_ITEMS:
                if item in dev_id:
                    device_dict[item] = dev_id[item]
            if 'Data' in dev_id:
                device_dict['Data'] = dict()
                for item in ApiClient.DATA_ITEMS:
                    if item in dev_id['Data']:
                        device_dict['Data'][item] = dev_id['Data'][item]
            if 'Point' in dev_id:
                device_dict['Point'] = dict()
                for item in ApiClient.POINT_ITEMS:
                    if item in dev_id['Point']:
                        device_dict['Point'][item] = dev_id['Point'][item]
            if 'Storm' in dev_id:
                device_dict['Storm'] = dict()
                for item in ApiClient.STORM_ITEMS:
                    if item in dev_id['Storm']:
                        device_dict['Storm'][item] = dev_id['Storm'][item]
            # perform any manipulation/translation of the API response data
            # (eg if no Storm device UV will be 9999, weeWX expects so UV field
            # or data is no sensor so delete the UV entry)
            device_dict.update(ApiClient.translate_data(device_dict,
                                                        ApiClient.TRANSLATIONS))
            device_list.append(device_dict)
        return device_list

    @staticmethod
    def translate_data(data, td):
        """Translate BloomSky API response data to meet WeeWX requirements."""

        # iterate over each item in the translation dict
        for key, value in td.items():
            # if the item is dict then recursively call ourself to translate
            # any fields in the child dict
            if hasattr(value, 'keys'):
                if key in data:
                    data[key].update(ApiClient.translate_data(data[key], value))
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
            data: Dict containing the translated API response
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
            data: Dict containing the translated API response
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
            # keep reference to the client we are supporting
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
        """Submit HTTP GET request and return any data as JSON object.

        Construct the GET request from its components. Submit the GET request
        and obtain the JSON format response. The JSON format response is
        returned without alteration.

        Inputs:
            url:
            params:
            headers:

        Returns:
            JSON format API response.
        """

        # encode the GET parameters
        data = urllib.parse.urlencode(params)
        # obtain an obfuscated copy of the API key being used for use when
        # logging
        obf = dict(headers)
        if 'Authorization' in obf:
            obf['Authorization'] = ''.join(("....", obf['Authorization'][-4:]))
        logdbg("url: %s data: %s hdr: %s" % (url, params, obf))
        # A urllib2.Request that includes a 'data' parameter value will be sent
        # as a POST request. the BloomSky API requires a GET request. So to
        # send as a GET request with data just append '?' and the 'data' to the
        # URL then create the request with just url and headers parameters.
        _url = ''.join((url, '?', data))
        # create a Request object
        req = urllib.request.Request(url=_url, headers=headers)
        try:
            # submit the request
            w = urllib.request.urlopen(req)
            # Get charset used so we can decode the stream correctly.
            # Unfortunately the way to get the charset depends on whether
            # we are running under python2 or python3. Assume python3 but be
            # prepared to catch the error if python2.
            try:
                char_set = w.headers.get_content_charset()
            except AttributeError:
                # must be python2
                char_set = w.headers.getparam('charset')
            # Now get the response and decode it using the headers character
            # set, BloomSky does not currently return a character set in its
            # API response headers so be prepared for charset==None.
            if char_set is not None:
                resp = w.read().decode(char_set)
            else:
                resp = w.read().decode()
            w.close()
        except (urllib.error.URLError, socket.timeout) as e:
            logerr("Failed to get BloomSky API data")
            logerr("   **** %s" % e)
        # convert the response to a JSON object
        resp_json = json.loads(resp)
        # log response as required
        logdbg3("JSON API response: %s" % json.dumps(resp_json))
        # return the JSON object
        return resp_json


# To test this driver, do one of the following depending on your WeeWX install
# type:
#   PYTHONPATH=/home/weewx/bin python /home/weewx/bin/user/bloomsky.py
# To use this driver in standalone mode for testing or development, use one of
# the following commands (depending on your weeWX install):
#
#   $ PYTHONPATH=/home/weewx/bin python /home/weewx/bin/user/bloomsky.py
#
#   or
#
#   $ PYTHONPATH=/usr/share/weewx python /usr/share/weewx/user/bloomsky.py
#
#   The above commands will display details of available command line options.

if __name__ == "__main__":
    usage = """%prog [options] [--help]"""

    def main():
        import optparse
        syslog.openlog('wee_bloomsky', syslog.LOG_PID | syslog.LOG_CONS)
        parser = optparse.OptionParser(usage=usage)
        parser.add_option('--version', dest='version', action='store_true',
                          help='display BloomSky driver version number')
        parser.add_option('--config', dest='config_path', metavar='CONFIG_FILE',
                          help="Use configuration file CONFIG_FILE.")
        parser.add_option('--debug', dest='debug', action='store_true',
                          help='display diagnostic information while running')
        parser.add_option('--run-driver', dest='run_driver', action='store_true',
                          metavar='RUN_DRIVER', help='run the BloomSky driver')
        parser.add_option('--api-key', dest='api_key', metavar='API_KEY',
                          help='BloomSky API key')
        parser.add_option('--get-json-data', dest='jdata', action='store_true',
                          help='get Bloomsky API json response')
        parser.add_option('--get-deviceids', dest='get_ids', action='store_true',
                          help='get Bloomsky device IDs associated with an API key')
        (opts, args) = parser.parse_args()

        # if --debug raise our log level
        if opts.debug:
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

        # display driver version number
        if opts.version:
            print("%s driver version: %s" % (DRIVER_NAME, DRIVER_VERSION))
            exit(0)

        # get config_dict to use
        config_path, config_dict = weecfg.read_config(opts.config_path, args)
        print "Using configuration file %s" % config_path
        stn_dict = config_dict.get('Bloomsky', {})

        # do we have a specific API key to use
        if opts.api_key:
            stn_dict['api_key'] = opts.api_key
            print "Using Bloomsky API key %s" % opts.api_key

        # display device IDs
        if opts.get_ids:
            get_ids(stn_dict)

        # run the driver
        if opts.run_driver:
            run_driver(stn_dict)

        # get BloomSky API JSON response
        # display Bloomsky API JSON response
        if opts.jdata:
            get_json_data(stn_dict)

    def get_ids(stn_dict):
        """Display Bloomsky device IDs associated with an API key."""

        # get a BloomskyDriver object
        driver = BloomskyDriver(**stn_dict)
        ids = driver.ids
        if len(ids) > 1:
            print "Found Bloomsky device IDs: %s" % ', '.join(ids)
        elif len(ids) == 1:
            print "Found Bloomsky device ID: %s" % ', '.join(ids)
        else:
            print "No Bloomsky device IDS found"
        driver.closePort()
        exit(0)

    def run_driver(stn_dict):
        """Run the Bloomsky driver."""

        import weeutil.weeutil

        # get a BloomskyDriver object
        driver = BloomskyDriver(**stn_dict)
        # wrap in a try..except so we can pickup a keyboard interrupt
        try:
            # continuously get loop packets and print them to screen
            for pkt in driver.genLoopPackets():
                print(weeutil.weeutil.timestamp_to_string(pkt['dateTime']), pkt)
        except KeyboardInterrupt:
            # we have a keyboard interrupt so shut down
            driver.closePort()

    def get_json_data(stn_dict):
        """Obtain Bloomsky API response and display in JSON format."""

        # extract the API key
        api_key = stn_dict.get('api_key')
        # if we have an API key then get the data otherwise exit after
        # informing the user about the problem
        if api_key:
            # get an ApiClient object
            api_client = ApiClient(api_key=api_key)
            # get the JSON response
            raw_data = api_client.sd.get_data()
            # display the JSON response on screen
            print json.dumps(raw_data, sort_keys=True, indent=2)
        else:
            print "Bloomsky API key required."
            print "Specify API key in configuration file under [Bloomsky] or use --api_key option."
            print "Exiting."
            exit(1)

    main()
