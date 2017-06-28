The Bloomsky driver is a weeWX driver that support the Bloomsky Sky1, Sky2 and
Storm personal weather stations. The driver utilises the Bloomsky API to obtain
observation data from the Bloomsky devices.

Pre-Requisites

The Bloomsky driver requires weeWX v3.7.0 or greater. A Bloomsky API key is
also required and can be obtained from dashboard.bloomsky.com.

Installation Instructions

Installation using the wee_extension utility

Note:   Symbolic names are used below to refer to some file location on the
weeWX system. These symbolic names allow a common name to be used to refer to
a directory that may be different from system to system. The following symbolic
names are used below:

-   $DOWNLOAD_ROOT. The path to the directory containing the downloaded
    Realtime gauge-data extension.

-   $BIN_ROOT. The path to the directory where weeWX executables are located.
    This directory varies depending on weeWX installation method. Refer to
    'where to find things' in the weeWX User's Guide:
    http://weewx.com/docs/usersguide.htm#Where_to_find_things for further
    information.

1.  Download the latest Bloomsky driver extension from the Bloomsky driver
releases page (https://github.com/gjr80/weewx-bloomsky/releases) into
a directory accessible from the weeWX machine.

    $ wget -P $DOWNLOAD_ROOT https://github.com/gjr80/weewx-bloomsky/releases/download/v0.1.0/bloomsky-0.1.0.tar.gz

	where $DOWNLOAD_ROOT is the path to the directory where the Bloomsky driver
    data extension is to be downloaded.

2.  Stop weeWX:

    $ sudo /etc/init.d/weewx stop

	or

    $ sudo service weewx stop

3.  Install the Bloomsky driver extension downloaded at step 1 using the
*wee_extension* utility:

    $ wee_extension --install=$DOWNLOAD_ROOT/bloomsky-0.1.0.tar.gz

    This will result in output similar to the following:

        Request to install '/var/tmp/bloomsky-0.1.0.tar.gz'
        Extracting from tar archive /var/tmp/bloomsky-0.1.0.tar.gz
        Saving installer file to /home/weewx/bin/user/installer/Bloomsky
        Saved configuration dictionary. Backup copy at /home/weewx/weewx.conf.20161123124410
        Finished installing extension '/var/tmp/bloomsky-0.1.0.tar.gz'

4.  Select and configure the driver:

    $ sudo wee_config --reconfigure

    selecting the Bloomsky (user.bloomsky) and providing the Bloomsky API key
    to be used when prompted

5.  Add the following stanza to weewx.conf:

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

5.  Start weeWX:

    $ sudo /etc/init.d/weewx start

	or

    $ sudo service weewx start

This will result in the driver collecting data from the bloomsky API and
emitting loop packets. The weeWX log may be monitored to confirm operation.
The Bloomsky driver installation can be further customized (eg sensor mapping,
polling interval etc) by referring to the Bloomsky driver extension wiki or the
comments at the start of the Bloomsky driver file $BIN_ROOT/user/bloomsky.py.

Manual installation

1.  Download the latest Bloomsky driver extension from the Bloomsky driver
releases page (https://github.com/gjr80/weewx-bloomsky/releases) into
a directory accessible from the weeWX machine.

    $ wget -P $DOWNLOAD_ROOT https://github.com/gjr80/weewx-bloomsky/releases/download/v0.1.0/bloomsky-0.1.0.tar.gz

	where $DOWNLOAD_ROOT is the path to the directory where the Bloomsky driver
    data extension is to be downloaded.

2.  Unpack the extension as follows:

    $ tar xvfz bloomsky-0.1.0.tar.gz

3.  Copy the bloomsky.py file from within the resulting folder as follows:

    $ cp bloomsky/bin/user/bloomsky.py $BIN_ROOT/user

	replacing the symbolic name $BIN_ROOT with the nominal location for your
    installation.

4.  Edit weewx.conf:

    $ vi weewx.conf

5.  Make the following changes to weewx,conf:

    - change the [Station] station_type config option to:

        [Station]
            ...
            station_type = Bloomsky

    -   add a [Bloomsky] stanza as follows:

        [Bloomsky]
            # This section is for the Bloomsky station

            # Bloomsky API key obtained from dashboard.bloomsky.com
            api_key = INSERT_API_KEY_HERE

            # Bloomsky claim data is updated from the station every 5-8 minutes.
            # How often in seconds the driver will poll the Bloomsky API. Default is
            # 60 seconds
            poll_interval = 60

            # The driver itself
            driver = user.bloomsky

    -   if it does not already exist add an [Accumulator] stanza as follows:

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

        if the [Accumulator] stanza already exists ensure the child config
        options above are added

6.  Start weeWX:

    $ sudo /etc/init.d/weewx start

	or

    $ sudo service weewx start

This will result in the driver collecting data from the bloomsky API and
emitting loop packets. The weeWX log may be monitored to confirm operation.
The Bloomsky driver installation can be further customized (eg sensor mapping,
polling interval etc) by referring to the Bloomsky driver extension wiki or the
comments at the start of the Bloomsky driver file $BIN_ROOT/user/bloomsky.py.
