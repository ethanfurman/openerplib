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

"""
OpenERP Client Library

Home page: http://pypi.python.org/pypi/openerp-client-lib
Code repository: https://code.launchpad.net/~niv-openerp/openerp-client-lib/trunk
"""

import xmlrpclib
import logging
import urllib2
import random
from aenum import Enum
from base64 import b64decode
from datetime import date, datetime
from dbf import Date, DateTime
from stoneleaf import AttrDict, Many2One
from scription import bytes, unicode

try:
    import json
except ImportError:
    import simplejson as json

DEFAULT_SERVER_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_SERVER_TIME_FORMAT = "%H:%M:%S"
DEFAULT_SERVER_DATETIME_FORMAT = "%s %s" % (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_TIME_FORMAT)

_logger = logging.getLogger(__name__)

def _getChildLogger(logger, subname):
    return logging.getLogger(logger.name + "." + subname)

class Connector(object):
    """
    The base abstract class representing a connection to an OpenERP Server.
    """

    __logger = _getChildLogger(_logger, 'connector')

    def get_service(self, service_name):
        """
        Returns a Service instance to allow easy manipulation of one of the services offered by the remote server.

        :param service_name: The name of the service.
        """
        return Service(self, service_name)

class XmlRPCConnector(Connector):
    """
    A type of connector that uses the XMLRPC protocol.
    """
    PROTOCOL = 'xmlrpc'

    __logger = _getChildLogger(_logger, 'connector.xmlrpc')

    def __init__(self, hostname, port=8069):
        """
        Initialize by specifying the hostname and the port.
        :param hostname: The hostname of the computer holding the instance of OpenERP.
        :param port: The port used by the OpenERP instance for XMLRPC (default to 8069).
        """
        self.url = 'http://%s:%d/xmlrpc' % (hostname, port)

    def send(self, service_name, method, *args):
        url = '%s/%s' % (self.url, service_name)
        service = xmlrpclib.ServerProxy(url)
        return getattr(service, method)(*args)

class XmlRPCSConnector(XmlRPCConnector):
    """
    A type of connector that uses the secured XMLRPC protocol.
    """
    PROTOCOL = 'xmlrpcs'

    __logger = _getChildLogger(_logger, 'connector.xmlrpcs')

    def __init__(self, hostname, port=8069):
        super(XmlRPCSConnector, self).__init__(hostname, port)
        self.url = 'https://%s:%d/xmlrpc' % (hostname, port)

class JsonRPCException(Exception):
    def __init__(self, error):
         self.error = error
    def __str__(self):
         return repr(self.error)

def json_rpc(url, fct_name, params):
    data = {
        "jsonrpc": "2.0",
        "method": fct_name,
        "params": params,
        "id": random.randint(0, 1000000000),
    }
    req = urllib2.Request(url=url, data=json.dumps(data), headers={
        "Content-Type":"application/json",
    })
    result = urllib2.urlopen(req)
    result = json.load(result)
    if result.get("error", None):
        raise JsonRPCException(result["error"])
    return result["result"]

class JsonRPCConnector(Connector):
    """
    A type of connector that uses the JsonRPC protocol.
    """
    PROTOCOL = 'jsonrpc'

    __logger = _getChildLogger(_logger, 'connector.jsonrpc')

    def __init__(self, hostname, port=8069):
        """
        Initialize by specifying the hostname and the port.
        :param hostname: The hostname of the computer holding the instance of OpenERP.
        :param port: The port used by the OpenERP instance for JsonRPC (default to 8069).
        """
        self.url = 'http://%s:%d/jsonrpc' % (hostname, port)

    def send(self, service_name, method, *args):
        return json_rpc(self.url, "call", {"service": service_name, "method": method, "args": args})

class JsonRPCSConnector(Connector):
    """
    A type of connector that uses the JsonRPC protocol.
    """
    PROTOCOL = 'jsonrpcs'

    __logger = _getChildLogger(_logger, 'connector.jsonrpc')

    def __init__(self, hostname, port=8069):
        """
        Initialize by specifying the hostname and the port.
        :param hostname: The hostname of the computer holding the instance of OpenERP.
        :param port: The port used by the OpenERP instance for JsonRPC (default to 8069).
        """
        self.url = 'https://%s:%d/jsonrpc' % (hostname, port)

    def send(self, service_name, method, *args):
        return json_rpc(self.url, "call", {"service": service_name, "method": method, "args": args})

class Service(object):
    """
    A class to execute RPC calls on a specific service of the remote server.
    """
    def __init__(self, connector, service_name):
        """
        :param connector: A valid Connector instance.
        :param service_name: The name of the service on the remote server.
        """
        self.connector = connector
        self.service_name = service_name
        self.__logger = _getChildLogger(_getChildLogger(_logger, 'service'),service_name or "")

    def __getattr__(self, method):
        """
        :param method: The name of the method to execute on the service.
        """
        self.__logger.debug('method: %r', method)
        def proxy(*args):
            """
            :param args: A list of values for the method
            """
            self.__logger.debug('args: %r', args)
            result = self.connector.send(self.service_name, method, *args)
            self.__logger.debug('result: %r', result)
            return result
        return proxy

class Connection(object):
    """
    A class to represent a connection with authentication to an OpenERP Server.
    It also provides utility methods to interact with the server more easily.
    """
    __logger = _getChildLogger(_logger, 'connection')

    def __init__(self, connector,
                 database=None,
                 login=None,
                 password=None,
                 user_id=None):
        """
        Initialize with login information. The login information is facultative to allow specifying
        it after the initialization of this object.

        :param connector: A valid Connector instance to send messages to the remote server.
        :param database: The name of the database to work on.
        :param login: The login of the user.
        :param password: The password of the user.
        :param user_id: The user id is a number identifying the user. This is only useful if you
        already know it, in most cases you don't need to specify it.
        """
        self.connector = connector

        self.set_login_info(database, login, password, user_id)
        self.user_context = None

    def set_login_info(self, database, login, password, user_id=None):
        """
        Set login information after the initialisation of this object.

        :param connector: A valid Connector instance to send messages to the remote server.
        :param database: The name of the database to work on.
        :param login: The login of the user.
        :param password: The password of the user.
        :param user_id: The user id is a number identifying the user. This is only useful if you
        already know it, in most cases you don't need to specify it.
        """
        self.database, self.login, self.password = database, login, password

        self.user_id = user_id

    def check_login(self, force=True):
        """
        Checks that the login information is valid. Throws an AuthenticationError if the
        authentication fails.

        :param force: Force to re-check even if this Connection was already validated previously.
        Default to True.
        """
        if self.user_id and not force:
            return

        if not self.database or not self.login or self.password is None:
            raise AuthenticationError("Credentials not provided")

        # TODO use authenticate instead of login
        self.user_id = self.get_service("common").login(self.database, self.login, self.password)
        if not self.user_id:
            raise AuthenticationError("Authentication failure")
        self.__logger.debug("Authenticated with user id %s", self.user_id)

    def get_user_context(self):
        """
        Query the default context of the user.
        """
        if not self.user_context:
            self.user_context = self.get_model('res.users').context_get()
        return self.user_context

    def get_model(self, model_name, transient=False):
        """
        Returns a Model instance to allow easy remote manipulation of an OpenERP model.

        :param model_name: The name of the model.
        """
        model = Model(self, model_name)
        if not transient:
            # make sure model is valid
            model.search([('id','=',0)])
        return model

    def get_service(self, service_name):
        """
        Returns a Service instance to allow easy manipulation of one of the services offered by the remote server.
        Please note this Connection instance does not need to have valid authentication information since authentication
        is only necessary for the "object" service that handles models.

        :param service_name: The name of the service.
        """
        return self.connector.get_service(service_name)

class AuthenticationError(Exception):
    """
    An error thrown when an authentication to an OpenERP server failed.
    """
    pass

class Model(object):
    """
    Useful class to dialog with one of the models provided by an OpenERP server.
    An instance of this class depends on a Connection instance with valid authentication information.
    """

    def __init__(self, connection, model_name):
        """
        :param connection: A valid Connection instance with correct authentication information.
        :param model_name: The name of the model.
        """
        self.connection = connection
        self.model_name = model_name
        self.__logger = _getChildLogger(_getChildLogger(_logger, 'object'), model_name or "")
        for key, value in self._get_vars_().items():
            setattr(self, key, value)
        self._columns = self.own_fields_get()
        self._all_columns = self.fields_get()
        id = AttrDict(
                type='integer',
                string='ID',
                readonly=True,
                )
        if 'id' not in self._columns:
            self._columns.id = id
        if 'id' not in self._all_columns:
            self._all_columns.id = id
        self._text_fields = []
        self._binary_fields = []
        self._many_fields = []
        self._date_fields = []
        self._datetime_fields = []
        for f, d in self._columns.items():
            if '.' in f:
                # TODO: ignoring mirrored fields
                continue
            if d['type'] in ('char', 'html', 'text'):
                self._text_fields.append(f)
            elif d['type'] in ('binary', ):
                self._binary_fields.append(f)
            elif d['type'] in ('one2many', 'many2many'):
                self._many_fields.append(f)
            elif d['type'] in ('date', ):
                self._date_fields.append(f)
            elif d['type'] in ('datetime', ):
                self._datetime_fields.append(f)

    def __getattr__(self, method):
        """
        Provides proxy methods that will forward calls to the model on the remote OpenERP server.

        :param method: The method for the linked model (search, read, write, unlink, create, ...)
        """
        def proxy(*args, **kwds):
            """
            :param args: A list of values for the method
            """
            self.connection.check_login(False)
            self.__logger.debug(args)
            #
            # pre-process
            #
            # ensure everything is marshalable
            new_args = []
            for i, a in enumerate(args):
                if isinstance(a, (AttrDict, dict, list, tuple)):
                    a = pfm(a)
                new_args.append(a)
            args = tuple(new_args)
            for k, v in kwds.items():
                if isinstance(v, (AttrDict, dict, list, tuple)):
                    kwds[k] = pfm(v)
            # method specific endeavors
            if method == 'create':
                # get the values, fields, and default values
                new_values = kwds.pop('values', None) or args[0]
                fields = self._all_columns
                default_values = self.default_get(fields.keys())
                # take special care with x2many fields 'cause they come to us as a list of
                # ids which we must transform into a list of delete and add commands such as
                # [(3, id1), (4, id1), (3, id2), (4, id2), ...]
                manies = [
                        k for (k, v) in fields.items()
                        if v['type'] in ('one2many', 'many2many')
                           and k in default_values
                           and k not in new_values
                           and default_values[k]
                        ]
                for many in manies:
                    new_many = []
                    for id in default_values[many]:
                        new_many.append((3, id))
                        new_many.append((4, id))
                    default_values[many] = new_many
                # finally, update the defaults from the passed in values
                default_values.update(new_values)
                args = (pfm(default_values), ) + args[1:]
            #
            elif method == 'read':
                # ids can actually be a domain, so support a domain keyword
                if 'domain' in kwds:
                    kwds['ids'] = kwds.pop('domain')
            #
            elif method == 'search':
                # 'domain' keyword is actualy 'args' (stupid), so switch 'domain' to 'args'
                # if present
                if 'domain' in kwds and 'args' in kwds:
                    raise ValueError('cannot specify both "args" and "domain"')
                elif 'domain' in kwds:
                    kwds['args'] = kwds['domain']
                    del kwds['domain']
            #
            elif method == 'write':
                # ensure values are OpenERP appropriate
                ids = kwds.pop('ids', None) or args[0]
                values = kwds.pop('values', None) or args[1]
                values = pfm(values)
                args = (ids, values) + args[2:]
            #
            # call method
            #
            result = self.connection.get_service('object').execute_kw(
                                                    self.connection.database,
                                                    self.connection.user_id,
                                                    self.connection.password,
                                                    self.model_name,
                                                    method,
                                                    args,
                                                    kwds
                                                    )
            #
            # post-process
            #
            if method == "read":
                one_only = False
                if isinstance(result, dict):
                    one_only = True
                    result = [result]
                if isinstance(result, list) and len(result) > 0 and "id" in result[0]:
                    # 'ids' may have been a domain, so get the actual ids from the
                    # returned records
                    ids = [r['id'] for r in result]
                    if 'fields' in kwds:
                        fields = kwds['fields']
                    elif len(args) > 1:
                        fields = args[1]
                    else:
                        fields = self._all_columns.keys()
                    # find all x2many fields and convert values to Many2One
                    # find all text fields and convert values to unicode
                    # find all binary fields and convert to bytes
                        # field_defs = self.fields_get(allfields=fields)
                    x2many = {}
                        # for f, d in field_defs.items():
                    for f in fields:
                        if f in self._text_fields:
                            for r in result:
                                if r[f] is False:
                                    continue
                                if not isinstance(r[f], unicode):
                                    r[f] = r[f].decode('utf-8')
                        elif f in self._binary_fields:
                            for r in result:
                                if r[f] is False:
                                    continue
                                if not isinstance(r[f], bytes):
                                    r[f] = b64decode(r[f].encode('utf-8'))
                                else:
                                    r[f] = b64decode(r[f])
                        elif f in self._date_fields:
                            for r in result:
                                if r[f] is False:
                                    continue
                                r[f] = Date.strptime(r[f], DEFAULT_SERVER_DATE_FORMAT)
                        elif f in self._datetime_fields:
                            for r in result:
                                if r[f] is False:
                                    continue
                                r[f] = DateTime.strptime(r[f], DEFAULT_SERVER_DATETIME_FORMAT)
                        elif f in self._many_fields:
                            link_table = self.connection.get_model(self._all_columns[f]['relation'])
                            link_ids = list(set([
                                    id
                                    for record in result
                                    for id in record[f]
                                    ]))
                            link_records = [
                                    Many2One(r.id, r[link_table._rec_name])
                                    for r in link_table.read(
                                            link_ids,
                                            fields=['id', link_table._rec_name],
                                            )]
                            x2many[f] = dict([
                                (m2o.id, m2o)
                                for m2o in link_records
                                ])
                            # and update the original records
                            for record in result:
                                record[f] = [x2many[f][id] for id in record[f]]
                    index = {}
                    for r in result:
                        index[r['id']] = _normalize(r, fields=fields)
                    result = [index[x] for x in ids if x in index]
                if one_only:
                    [result] = result
            elif isinstance(result, dict):
                try:
                    result = _normalize(result)
                except Exception:
                    pass
            elif isinstance(result, (list, tuple)):
                try:
                    new_result = []
                    for v in result:
                        if isinstance(v, dict):
                            v = _normalize(v)
                        new_result.append(v)
                    result = type(result)(new_result)
                except Exception:
                    pass
            #
            self.__logger.debug('result: %r', result)
            return result
        return proxy

    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, context=None):
        """
        A shortcut method to combine a search() and a read().

        :param domain: The domain for the search.
        :param fields: The fields to extract (can be None or [] to extract all fields).
        :param offset: The offset for the rows to read.
        :param limit: The maximum number of rows to read.
        :param order: The order to class the rows.
        :param context: The context.
        :return: A list of dictionaries containing all the specified fields.
        """
        record_ids = self.search(domain or [], offset, limit or False, order or False, context or {})
        if not record_ids: return []
        records = self.read(record_ids, fields or [], context or {})
        return records

def get_connector(hostname=None, protocol="xmlrpc", port="auto"):
    """
    A shortcut method to easily create a connector to a remote server using XMLRPC.

    :param hostname: The hostname to the remote server.
    :param protocol: The name of the protocol, must be "xmlrpc", "xmlrpcs", "jsonrpc" or "jsonrpcs".
    :param port: The number of the port. Defaults to auto.
    """
    if port == 'auto':
        port = 8069
    if protocol == "xmlrpc":
        return XmlRPCConnector(hostname, port)
    elif protocol == "xmlrpcs":
        return XmlRPCSConnector(hostname, port)
    if protocol == "jsonrpc":
        return JsonRPCConnector(hostname, port)
    elif protocol == "jsonrpcs":
        return JsonRPCSConnector(hostname, port)
    else:
        raise ValueError("You must choose xmlrpc, xmlrpcs, jsonrpc or jsonrpcs")

def get_connection(hostname=None, protocol="xmlrpc", port='auto', database=None,
                 login=None, password=None, user_id=None, skip_check=False):
    """
    A shortcut method to easily create a connection to a remote OpenERP server.

    :param hostname: The hostname to the remote server.
    :param protocol: The name of the protocol, must be "xmlrpc", "xmlrpcs", "jsonrpc" or "jsonrpcs".
    :param port: The number of the port. Defaults to auto.
    :param connector: A valid Connector instance to send messages to the remote server.
    :param database: The name of the database to work on.
    :param login: The login of the user.
    :param password: The password of the user.
    :param user_id: The user id is a number identifying the user. This is only useful if you
    already know it, in most cases you don't need to specify it.
    """
    connection = Connection(get_connector(hostname, protocol, port), database, login, password, user_id)
    # if necessary paramaters given, ensure valid connection unless skip_check is True
    if hostname and database and login and password and not skip_check:
        connection.get_model('res.users').search([('id','=',0)])
    return connection

def _normalize(d, fields=None):
    'recursively convert each dict into a AttrDict'
    # fields may be modified
    res = AttrDict()
    if fields is None:
        fields = d.keys()
    if 'id' in d and 'id' not in fields:
        fields.insert(0, 'id')
    other = set(d.keys()) - set(fields)
    fields.extend(list(other))
    for key in fields:
        if '.' in key:
            # TODO: ignoring mirrored fields
            continue
        value = d[key]
        if isinstance(value, dict):
            res[key] = _normalize(value)
        elif isinstance(value, list) and value and isinstance(value[0], dict) and not isinstance(value[0], AttrDict):
            res[key] = [_normalize(v) for v in value]
        elif (
                isinstance(value, list)
            and len(value) == 2
            and isinstance(value[0], (int, long))
            and isinstance(value[1], basestring)
            ):
            res[key] = Many2One(*value)
        else:
            res[key] = value
    return res

def pfm(values):
    if isinstance(values, (dict, AttrDict)):
        new_values = {}
        for k, v in values.items():
            if not v and isinstance(v, (str, int, long)):
                new_values[k] = False
            elif isinstance(v, (date, Date)):
                new_values[k] = v.strftime(DEFAULT_SERVER_DATE_FORMAT)
            elif isinstance(v, (datetime, DateTime)):
                new_values[k] = v.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            elif isinstance(v, Many2One):
                new_values[k] = v.id
            elif isinstance(v, Enum):
                new_values[k] = v.value
            elif isinstance(v, (dict, AttrDict, list, tuple)):
                new_values[k] = pfm(v)
            else:
                new_values[k] = v
        return new_values
    elif isinstance(values, Many2One):
        return values.id
    elif isinstance(values, (list, tuple)):
        new_list = []
        for v in values:
            if not v and isinstance(v, (str, int, long)):
                new_list.append(False)
            elif isinstance(v, (date, Date)):
                new_list.append(v.strftime(DEFAULT_SERVER_DATE_FORMAT))
            elif isinstance(v, (datetime, DateTime)):
                new_list.append(v.strftime(DEFAULT_SERVER_DATETIME_FORMAT))
            elif isinstance(v, Many2One):
                new_list.append(v.id)
            elif isinstance(v, Enum):
                new_list.append(v.value)
            elif isinstance(v, (dict, AttrDict, list, tuple)):
                new_list.append(pfm(v))
            else:
                new_list.append(v)
        return type(values)(new_list)
    else:
        raise ValueError('not sure how to convert %r' % (values, ))

class OpenERP(object):

    def __init__(self, host, database=None, login=None, password=None, protocol="xmlrpc", port='auto'):
        self.connection = get_connection(host, protocol, port, database, login, password)

    def __getattr__(self, model):
        setattr(self, model, self.connection.get_model(model))

