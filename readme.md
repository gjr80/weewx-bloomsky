# BloomSky Sky1/Sky2/Storm Driver #

## Description ##

The BloomSky driver is a WeeWX driver that supports the BloomSky Sky1, Sky2 and Storm personal weather stations. The driver utilises the BloomSky API to obtain observation data from the BloomSky devices.

## Pre-Requisites ##

The BloomSky driver requires WeeWX v3.7.0 or greater. Both Python 2 and Python 3 are supported when using WeeWX v4.0.0 or later. A BloomSky API key is also required and can be obtained from [dashboard.bloomsky.com](dashboard.bloomsky.com).

## Installation Instructions ##

### Installation using the *wee_extension* utility ###

**Note**:   Symbolic names are used below to refer to some file location on the WeeWX system. These symbolic names allow a common name to be used to refer to a directory that may be different from system to system. The following symbolic names are used below:

-   *$DOWNLOAD_ROOT*. The path to the directory containing the downloaded BloomSky driver extension.

-   *$BIN_ROOT*. The path to the directory where WeeWX executables are located. This directory varies depending on WeeWX installation method. Refer to [where to find things](http://weewx.com/docs/usersguide.htm#Where_to_find_things) in the WeeWX User's Guide for further information.

1.  Download the latest BloomSky driver extension from the [Bloomsky driver releases page](https://github.com/gjr80/weewx-bloomsky/releases) into a directory accessible from the WeeWX machine.

        $ wget -P $DOWNLOAD_ROOT https://github.com/gjr80/weewx-bloomsky/releases/download/v2.0.1/bloomsky-2.0.1.tar.gz

    where *$DOWNLOAD_ROOT* is the path to the directory where the BloomSky driver extension is to be downloaded.

1.  Stop WeeWX:

        $ sudo /etc/init.d/weewx stop

    or

        $ sudo service weewx stop
        
    or
    
        $ sudo systemctl stop weewx

1.  Install the BloomSky driver extension downloaded at step 1 using the *wee_extension* utility:

        $ wee_extension --install=$DOWNLOAD_ROOT/bloomsky-2.0.1.tar.gz

    This will result in output similar to the following:

        Request to install '/var/tmp/bloomsky-2.0.1.tar.gz'
        Extracting from tar archive /var/tmp/bloomsky-2.0.1.tar.gz
        Saving installer file to /home/weewx/bin/user/installer/Bloomsky
        Saved configuration dictionary. Backup copy at /home/weewx/weewx.conf.20200523124410
        Finished installing extension '/var/tmp/bloomsky-2.0.1.tar.gz'

1.  Select and configure the driver:

        $ sudo wee_config --reconfigure

    selecting *BloomSky (user.bloomsky)* and providing the BloomSky API key to be used when prompted.
    
    **Note**: If you do not yet have a BloomSky API key enter a fictitious API key and later when you do have an API key edit weewx.conf and set the *[Bloomsky] api_key* option appropriately.

1.  Add the following stanza to *weewx.conf*:

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

1.  Start WeeWX:

        $ sudo /etc/init.d/weewx start

    or

        $ sudo service weewx start
        
    or
    
        $ sudo systemctl start weewx

This will result in the driver collecting data from the bloomsky API and emitting loop packets. The WeeWX log may be monitored to confirm operation. The BloomSky driver installation can be further customized (eg sensor mapping, polling interval etc) by referring to the BloomSky driver extension wiki or the comments at the start of the BloomSky driver file *$BIN_ROOT/user/bloomsky.py*.

### Manual installation ###

1.  Download the latest BloomSky driver extension from the [Bloomsky driver releases page](https://github.com/gjr80/weewx-bloomsky/releases) into a directory accessible from the WeeWX machine.

        $ wget -P $DOWNLOAD_ROOT https://github.com/gjr80/weewx-bloomsky/releases/download/v2.0.1/bloomsky-2.0.1.tar.gz

    where *$DOWNLOAD_ROOT* is the path to the directory where the BloomSky driver extension is to be downloaded.

1.  Unpack the extension as follows:

        $ tar xvfz bloomsky-2.0.1.tar.gz

1.  Copy the *bloomsky.py* file from within the resulting folder as follows:

        $ cp bloomsky/bin/user/bloomsky.py $BIN_ROOT/user

    replacing the symbolic name *$BIN_ROOT* with the nominal location for your installation.

1.  Edit *weewx.conf*:

        $ nano weewx.conf

1.  Make the following changes to *weewx.conf*:

    - change the *[Station] station_type* config option to:

            [Station]
                ...
                station_type = Bloomsky

    -   add a *[Bloomsky]* stanza as follows:

            [Bloomsky]
                # This section is for the BloomSky station
    
                # BloomSky API key obtained from dashboard.bloomsky.com
                api_key = INSERT_API_KEY_HERE
    
                # BloomSky claim data is updated from the station every 5-8 minutes.
                # How often in seconds the driver will poll the BloomSky API. Default is
                # 60 seconds
                poll_interval = 60
    
                # The driver itself
                driver = user.bloomsky

    -   if it does not already exist add an *[Accumulator]* stanza as follows:

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

        if the *[Accumulator]* stanza already exists ensure the child config options above are added.

1.  Start WeeWX:

        $ sudo /etc/init.d/weewx start

    or

        $ sudo service weewx start
        
    or
    
        $ sudo systemctl start weewx

This will result in the driver collecting data from the bloomsky API and emitting loop packets. The WeeWX log may be monitored to confirm operation. The BloomSky driver installation can be further customized (eg sensor mapping, polling interval etc) by referring to the BloomSky driver extension wiki or the comments at the start of the BloomSky driver file *$BIN_ROOT/user/bloomsky.py*.
