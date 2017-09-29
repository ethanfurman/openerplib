# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (C) Stephane Wirtel
# Copyright (C) 2011 Nicolas Vanhoren
# Copyright (C) 2011 OpenERP s.a. (<http://openerp.com>).
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
##############################################################################

from time import timezone as system_timezone
from datetime import date, datetime, time
from pytz import timezone, utc as UTC

"""
str_* functions return objects in LOCAL_TIME
*_str functions return strings in UTC

whether those are different depends on whether the timezone is set on the server
"""

DEFAULT_SERVER_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_SERVER_TIME_FORMAT = "%H:%M:%S"
DEFAULT_SERVER_DATETIME_FORMAT = "%s %s" % (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_TIME_FORMAT)

# default to UTC
LOCAL_TIME = UTC
if system_timezone:
    try:
        with open('/etc/timezone') as tz:
            LOCAL_TIME = timezone(tz.read().strip())
    except Exception:
        pass

def str_to_datetime(string):
    """
    Converts a string to a datetime object using OpenERP's
    datetime string format (exemple: '2011-12-01 15:12:35').

    The UTC timezone is added, and then the datetime is converted
    to the local timezone.
    """
    if not string:
        return False
    dt = datetime.strptime(string.split(".")[0], DEFAULT_SERVER_DATETIME_FORMAT)
    dt = UTC.localize(dt).astimezone(LOCAL_TIME)
    return dt

def str_to_date(string):
    """
    Converts a string to a date object using OpenERP's
    date string format (exemple: '2011-12-01').
    """
    if not string:
        return False
    return date.strptime(string, DEFAULT_SERVER_DATE_FORMAT)

def str_to_time(string):
    """
    Converts a string to a time object using OpenERP's
    time string format (exemple: '15:12:35').

    The UTC timezone is added, and then the time is converted
    to the local timezone.
    """
    if not string:
        return False
    t = time.strptime(string.split(".")[0], DEFAULT_SERVER_TIME_FORMAT)
    dt = UTC.localize(datetime.combine(date.today(), t))
    dt = dt.astimezone(LOCAL_TIME)
    t = LOCAL_TIME.normalize(LOCAL_TIME.localize(dt.time()))
    return t

def datetime_to_str(dt):
    """
    Converts a datetime object to a string using OpenERP's
    datetime string format (exemple: '2011-12-01 15:12:35').

    If the datetime instance has an attached timezone it will be converted
    to UTC.
    """
    if not dt:
        return False
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC)
    return dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

def date_to_str(d):
    """
    Converts a date object to a string using OpenERP's
    date string format (exemple: '2011-12-01').
    """
    if not d:
        return False
    return d.strftime(DEFAULT_SERVER_DATE_FORMAT)

def time_to_str(t):
    """
    Converts a time object to a string using OpenERP's
    time string format (exemple: '15:12:35').

    If the datetime instance has an attached timezone it will be converted
    to UTC.
    """
    if not t:
        return False
    if t.tzinfo is not None:
        dt = datetime.combine(date.today(), t)
        dt = dt.astimezone(UTC)
        t = dt.time()
    return t.strftime(DEFAULT_SERVER_TIME_FORMAT)

def utc_datetime():
    utc_dt = local_datetime().astimezone(UTC)
    return utc_dt

def local_datetime():
    # same as utc if timezone not set
    dt = datetime.now()
    dt = LOCAL_TIME.normalize(LOCAL_TIME.localize(dt))
    return dt
