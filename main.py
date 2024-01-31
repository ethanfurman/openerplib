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
from __future__ import print_function
try:
    from xmlrpclib import Fault, ServerProxy
except ImportError:
    from xmlrpc.client import Fault, ServerProxy

try:
    from urllib2 import Request, urlopen
except ImportError:
    from urllib.request import Request, urlopen

try:
    import __builtin__ as builtins
except ImportError:
    import builtins

import logging
import random
import re
from aenum import Enum, NamedTuple
from base64 import b64decode
from .dates import local_to_utc, UTC
from datetime import date, datetime
from dbf import Date, DateTime
from .utils import AttrDict, IDEquality, Many2One, XidRec, Phone, Binary, SelectionEnum
from scription import bytes, integer as baseinteger, basestring, number, str, Var, raise_exc
from VSS.address import PostalCode

try:
    import json
except ImportError:
    import simplejson as json

DEFAULT_SERVER_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_SERVER_TIME_FORMAT = "%H:%M:%S"
DEFAULT_SERVER_DATETIME_FORMAT = "%s %s" % (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_TIME_FORMAT)

python_exc = Var(lambda hay: re.search(r"\\n(ValueError|KeyError): *(.*)\\n'>", hay))
oe_exc = Var(lambda hay: re.search(r"(AccessDenied|AccessError|MissingError|ValidationError|ConstraintError): (.*)\\n'>", hay))

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
        service = ServerProxy(url)
        try:
            return getattr(service, method)(*args)
        except Fault as exc1:
            exc = str(exc1)
            if oe_exc(exc):
                error, msg = oe_exc.groups()
                if msg.endswith(": ''"):
                    msg = msg[:-4]
                try:
                    exc2 = '%s%s' % (error, msg)
                    exc2 = eval(exc2.replace('\\',''))
                    raise_exc(exc2, cause=None)
                except KeyError:
                    raise exc1
            if python_exc(exc):
                error, msg = python_exc.groups()
                try:
                    exc2 = getattr(builtins, error)
                except:
                    raise exc1
                else:
                    # exc2 = exc2(msg)
                    # exc2.__cause__ = None
                    # raise exc2
                    raise_exc(exc2(msg), cause=None)
            raise


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
    req = Request(url=url, data=json.dumps(data), headers={
        "Content-Type":"application/json",
    })
    result = urlopen(req)
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
                 user_id=None,
                 raw=False
                 ):
        """
        Initialize with login information. The login information is facultative to allow specifying
        it after the initialization of this object.

        :param connector: A valid Connector instance to send messages to the remote server.
        :param database: The name of the database to work on.
        :param login: The login of the user.
        :param password: The password of the user.
        :param user_id: The user id is a number identifying the user. This is only useful if you
        already know it, in most cases you don't need to specify it.
        :param raw: True returns data as-is, False converts data to Python objects.
        """
        self.connector = connector

        self.set_login_info(database, login, password, user_id)
        self.user_context = None
        self.raw = raw

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
        try:
            model = Model(self, model_name, raw=self.raw)
        except Exception as exc:
            if "Object %s doesn't exist" % model_name in str(exc):
                raise MissingTable("Model '%s' doesn't exist" % model_name)
            raise
        if model._auto and not (model._transient or transient):
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

class MissingTable(Exception):
    "table not found in OpenERP"

class ValidateError(Exception):
    "failed constraint or missing selection"

class Model(object):
    """
    Useful class to dialog with one of the models provided by an OpenERP server.
    An instance of this class depends on a Connection instance with valid authentication information.
    """

    ir_model_data = None

    def __init__(self, connection, model_name, raw=False):
        """
        :param connection: A valid Connection instance with correct authentication information.
        :param model_name: The name of the model.
        """
        self._text_fields = set()
        self._html_fields = set()
        self._raw_html_fields = set()
        self._binary_fields = set()
        self._x2one_fields = set()
        self._x2many_fields = set()
        self._date_fields = set()
        self._datetime_fields = set()
        self._boolean_fields = set()
        self._integer_fields = set()
        self._float_fields = set()
        self._selection_fields = {}
        self._enum_fields = {}
        self._as_dbf = {}
        if self.ir_model_data is None and model_name != 'ir.model.data':
            self.__class__.ir_model_data = self.__class__(connection, 'ir.model.data')
        self.connection = connection
        self.model_name = model_name
        self.raw = raw
        self.__logger = _getChildLogger(_getChildLogger(_logger, 'object'), model_name or "")
        for key, value in self.model_info().items():
            setattr(self, key, value)
        self._all_columns = self.fields_get()
        id = AttrDict(
                type='integer',
                string='ID',
                readonly=True,
                )
        if 'id' not in self._all_columns:
            self._all_columns['id'] = id
        for f, d in self._all_columns.items():
            if '.' in f:
                # TODO: ignoring mirrored fields
                continue
            fld_type = d['type']
            dfn = dbf_field_name(f)
            if fld_type == 'raw_html':
                self._raw_html_fields.add(f)
            if fld_type == 'html':
                self._html_fields.add(f)
            if fld_type in ('char', 'html', 'raw_html', 'text'):
                self._text_fields.add(f)
                if d.get('size', 1024) < 129:
                    dft = 'C(%d)' % d['size']
                else:
                    dft = 'M'
            elif fld_type in ('binary', ):
                self._binary_fields.add(f)
                dft = 'M binary'
            elif fld_type in ('many2one', ):
                self._x2one_fields.add(f)
                dft = 'C(128)'
            elif fld_type in ('one2many', 'many2many'):
                self._x2many_fields.add(f)
                dft = 'M'
            elif fld_type in ('date', ):
                self._date_fields.add(f)
                dft = 'D'
            elif fld_type in ('datetime', ):
                self._datetime_fields.add(f)
                dft = 'T'
            elif fld_type in ('boolean', ):
                self._boolean_fields.add(f)
                dft = 'L'
            elif fld_type in ('integer', ):
                self._integer_fields.add(f)
                dft = 'N(17,0)'
            elif fld_type in ('float', ):
                self._float_fields.add(f)
                digits = d.get('digits')
                digits = tuple(digits) if digits else (17, 3)
                dft = 'N(%d, %d)' % digits
            elif fld_type in ('selection', ):
                size = 1
                items = {}
                for db, ud in d['selection']:
                    db = db and str(db) or u''
                    size = max(size, len(db))
                    items[ud] = db
                self._selection_fields[f] = items
                if size < 129:
                    dft = 'C(%d)' % size
                else:
                    dft = 'M'
                enum = d.get('enum')
                if enum:
                    name = enum[0]
                    items = [(m[0], tuple(m[1])) for m in enum[1:]]
                    enum = SelectionEnum(name, items)
                    self._enum_fields[f] = enum
                    setattr(self, name, enum)
            else:
                dft = 'M'
            self._as_dbf[f] = DbfNameSpec(dfn, '%s %s' % (dfn, dft))

    def __getattr__(self, method):
        """
        Provides proxy methods that will forward calls to the model on the remote OpenERP server.

        :param method: The method for the linked model (search, read, write, unlink, create, ...)
        """
        def proxy(*args, **kwds):
            """
            :param args: A list of values for the method
            """
            self.__logger.debug(method)
            self.__logger.debug('args: %r   kwds: %r', args, kwds)
            self.connection.check_login(False)
            #
            # pre-process
            #
            # method specific endeavors
            if method == 'create':
                imd_info = kwds.pop('imd_info', None)
                if imd_info and not isinstance(imd_info, AttrDict):
                    imd_info = AttrDict(**imd_info)
                # get the values, fields, and default values
                new_values = kwds.pop('values', None) or args[0]
                if imd_info is None and isinstance(new_values, XidRec):
                    imd_info = new_values._imd
                fields = self._all_columns
                default_values = self.default_get(fields.keys())
                # take special care with x2many fields 'cause they come to us as a list of
                # ids which we must transform into a list of delete and add commands such as
                # [(3, id1), (4, id1), (3, id2), (4, id2), ...]
                for source in (default_values, new_values):
                    manies = [
                            k for (k, v) in fields.items()
                            if v['type'] in ('one2many', 'many2many')
                            and k in source
                            ]
                    for many in manies:
                        new_many = []
                        for id in source[many]:
                            if isinstance(id, baseinteger):
                                # new_many.append((3, id))
                                new_many.append((4, id))
                            else:
                                new_many.append(id)
                        source[many] = new_many
                # update the defaults from the passed in values
                default_values.update(new_values)
                args = (default_values, ) + args[1:]
                self.__logger.debug('args: %r   kwds: %r', args, kwds)
            #
            elif method == 'read':
                # convert any kwds to args
                # - ids, fields, context (optional)
                # ids can actually be a domain, so support a domain keyword
                if 'domain' in kwds:
                    kwds['ids'] = kwds.pop('domain')
                if 'ids' in kwds:
                    if args:
                        # error, let OpenERP handle it
                        pass
                    else:
                        args = (kwds.pop('ids'), )
                if 'fields' in kwds:
                    args += (kwds.pop('fields'), )
                if len(args) < 3:
                    if 'context' not in kwds:
                        kwds['context'] = {}
                    kwds['context']['active_test'] = False
                else:
                    try:
                        if 'active_test' not in args[2]:
                            args[2]['active_test'] = False
                    except Exception:
                        pass
            #
            elif method == 'search':
                # 'domain' keyword is actualy 'args' (stupid), so switch 'domain' to 'args'
                # if present
                if 'domain' in kwds and 'args' in kwds:
                    raise ValueError('cannot specify both "args" and "domain"')
                elif 'domain' in kwds:
                    kwds['args'] = kwds['domain']
                    del kwds['domain']
                kwds.setdefault('context', {})['active_test'] = False
            #
            elif method == 'write':
                # ensure values are OpenERP appropriate
                ids = kwds.pop('ids', None) or args[0]
                values = kwds.pop('values', None) or args[1]
                fields = self._all_columns
                manies = [
                        k for (k, v) in fields.items()
                        if v['type'] in ('one2many', 'many2many')
                        and k in values
                        ]
                for many in manies:
                    new_many = []
                    for id in values[many]:
                        if isinstance(id, baseinteger):
                            # new_many.append((3, id))
                            new_many.append((4, id))
                        else:
                            new_many.append(id)
                    values[many] = new_many
                args = (ids, values) + args[2:]
            #
            # ensure everything is marshalable
            #
            new_args = []
            for i, a in enumerate(args):
                if isinstance(a, (AttrDict, dict, list, tuple)):
                    a = pfm(a)
                new_args.append(a)
            args = tuple(new_args)
            for k, v in kwds.items():
                if isinstance(v, (AttrDict, dict, list, tuple)):
                    kwds[k] = pfm(v)
            #
            # call method
            #
            # print('model: %r\n  args: %r\n  kwds: %r' % (self.model_name, args, kwds))
            result = self.connection.get_service('object').execute_kw(
                                                    self.connection.database,
                                                    self.connection.user_id,
                                                    self.connection.password,
                                                    self.model_name,
                                                    method,
                                                    args,
                                                    kwds
                                                    )
            self.__logger.debug('immediate result: %r', result)
            #
            # post-process
            #
            if method == "create":
                if imd_info:
                    imd_info.res_id = result
                    imd_info.pop('id', None)
                    try:
                        imd_info.id = self.ir_model_data.create(pfm(imd_info))
                    except Fault as exc:
                        if "multiple records with the same external ID" in str(exc):
                            # if existing record points to nothing, update it
                            [pos_rec_ptr] = self.ir_model_data.search_read(
                                    domain=[('module','=',imd_info.module),('name','=',imd_info.name)],
                                    fields=['id','model','res_id'],
                                    )
                            pos_recs = self.__class__(self.connection, pos_rec_ptr.model).read(
                                    pos_rec_ptr.res_id,
                                    fields=['id'],
                                    )
                            if not pos_recs:
                                # orphaned pointer, update it
                                self.ir_model_data.write(pos_rec_ptr.id, pfm(imd_info))
                                imd_info.id = pos_rec_ptr.id
                                return result
                        # something went wrong, delete the newly created record
                        self.unlink(result)
                        raise
            elif method == "unlink" and result and self.model_name != 'ir.model.data':
                # find any matching records in ir.model.data and delete them
                if args:
                    ids = args[0]
                else:
                    ids = kwds['ids']
                if isinstance(ids, baseinteger):
                    ids = [ids]
                target_imd_ids = [
                        r.id
                        for r in self.ir_model_data.search_read(
                            domain=[('model','=',self.model_name),('res_id','in',ids)],
                            context={'active_test': False},
                            )]
                if not self.ir_model_data.unlink(target_imd_ids):
                    # too late to not delete the original records, but we can emit an error
                    _logger.error('unable to remove %r ids from ir.model.data: %r' % (self.model_name, ids))
            elif self.raw:
                # skip any conversions of returned data
                pass
            elif method == "read":
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
                        fields = list(self._all_columns.keys())
                    # check for duplicates in fields
                    if len(fields) != len(set(fields)):
                        seen = set()
                        duplicates = []
                        for f in fields:
                            if f in seen:
                                duplicates.append(f)
                            else:
                                seen.add(f)
                        raise ValueError('duplicate name(s) in `fields`: %s' % ', '.join(sorted(duplicates)))
                    # find all x2many fields and convert values to Many2One
                    # find all text fields and convert values to unicode
                    # find all binary fields and convert to bytes
                    # find all selection enums and convert values to enum (or None)
                        # field_defs = self.fields_get(allfields=fields)
                    x2many = {}
                        # for f, d in field_defs.items():
                    for f in fields:
                        if f in self._text_fields:
                            for r in result:
                                if not r[f]:
                                    r[f] = None
                                elif isinstance(r[f], bytes):
                                    r[f] = r[f].decode('utf-8')
                                if f in ('fax', 'phone'):
                                    r[f] = Phone(r[f])
                        elif f in self._binary_fields:
                            for r in result:
                                try:
                                    if not r[f]:
                                        r[f] = None
                                    elif isinstance(r[f], (dict, list, tuple)):
                                        r[f] = Binary(r[f])
                                    elif not isinstance(r[f], bytes):
                                        r[f] = Binary(b64decode(r[f].encode('utf-8')))
                                    else:
                                        r[f] = Binary(b64decode(r[f]))
                                except:
                                    r[f] = Binary(r[f])
                        elif f in self._date_fields:
                            for r in result:
                                if not r[f]:
                                    r[f] = None
                                else:
                                    r[f] = Date.strptime(r[f][:10], DEFAULT_SERVER_DATE_FORMAT)
                        elif f in self._datetime_fields:
                            for r in result:
                                if not r[f]:
                                    r[f] = None
                                else:
                                    r[f] = DateTime.strptime(r[f].split('.')[0], DEFAULT_SERVER_DATETIME_FORMAT).replace(tzinfo=UTC)
                        elif f in self._enum_fields:
                            enum = self._enum_fields[f]
                            for r in result:
                                if not r[f]:
                                    r[f] = None
                                else:
                                    r[f] = enum(r[f])
                        elif f in self._selection_fields:
                            for r in result:
                                if not r[f]:
                                    r[f] = None
                                else:
                                    r[f] = str(r[f])
                        elif f in self._x2one_fields:
                            link_table_name = self._all_columns[f]['relation']
                            for r in result:
                                if not r[f]:
                                    r[f] = None
                                else:
                                    # r[f] == [id, text]
                                    r[f] = Many2One(r[f][0], r[f][1], link_table_name)
                        elif f in self._x2many_fields:
                            link_table_name = self._all_columns[f]['relation']
                            link_table = self.connection.get_model(link_table_name)
                            link_ids = list(set([
                                    id
                                    for record in result
                                    for id in record[f]
                                    ]))
                            link_fields = ['id']
                            if link_table._rec_name != 'id':
                                link_fields.append(link_table._rec_name)
                            link_records = [
                                    Many2One(r.id, r[link_table._rec_name], link_table_name)
                                    for r in link_table.read(
                                            link_ids,
                                            fields=link_fields,
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
                        index[r['id']] = self._normalize(r, fields=fields)
                    result = [index[x] for x in ids if x in index]
                # print('*' * 50)
                # print('returning from OE: %r' % result[0])
                if one_only:
                    [result] = result
            elif isinstance(result, dict):
                try:
                    result = self._normalize(result)
                except Exception:
                    pass
            elif isinstance(result, (list, tuple)):
                try:
                    new_result = []
                    for v in result:
                        if isinstance(v, dict):
                            v = self._normalize(v)
                        new_result.append(v)
                    result = type(result)(new_result)
                except Exception:
                    pass
            #
            self.__logger.debug('final result: %r', result)
            return result
        return proxy

    def __repr__(self):
        return "Model(%r, raw=%r)" % (self.model_name, self.raw)

    def _normalize(self, d, fields=None, type=AttrDict):
        'recursively convert each dict into an AttrDict'
        # fields may be modified
        fields = list(fields or d.keys())
        if 'id' in d and 'id' not in fields:
            fields.insert(0, 'id')
        other = set(d.keys()) - set(fields)
        fields.extend(list(other))
        res = AttrDict()
        for key in fields:

            # if '.' in key:
            #     # TODO: ignoring mirrored fields
            #     continue
            value = d[key]
            try:
                if isinstance(value, dict):
                    res[key] = self._normalize(value)
                elif isinstance(value, list) and value and isinstance(value[0], dict) and not isinstance(value[0], AttrDict):
                    res[key] = [self._normalize(v) for v in value]
                elif (
                        isinstance(value, list)
                    and len(value) == 2
                    and isinstance(value[0], baseinteger)
                    and isinstance(value[1], basestring)
                    ):
                    res[key] = Many2One(*(value + [self._all_columns[key].relation]))
                elif key in self._boolean_fields:
                    res[key] = value
                else:
                    res[key] = None if value is False else value
            except TypeError:
                print('\nkey = %r\nvalue = %r\nself._boolean_fields = %r' % (key, value, self._boolean_fields))
        return res


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
        # check for duplicates in fields
        fields = fields or (self._all_columns.keys())
        if len(fields) != len(set(fields)):
            seen = set()
            duplicates = []
            for f in fields:
                if f in seen:
                    duplicates.append(f)
                else:
                    seen.add(f)
            raise ValueError('duplicate name(s) in `fields`: %s' % ', '.join(sorted(duplicates)))
        record_ids = self.search(domain or [], offset, limit or False, order or False, context=context or {})
        if not record_ids: return []
        records = self.read(record_ids, fields, context or {})
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
                 login=None, password=None, user_id=None, skip_check=False, raw=False,
                 ):
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
    :param skip_check: False verifies that model exists.
    :param raw: True returns data as-is, False converts data to Python objects.
    """
    connection = Connection(
            get_connector(hostname, protocol, port),
            database, login, password, user_id, raw,
            )
    # if necessary paramaters given, ensure valid connection unless skip_check is True
    if hostname and database and login and password and not skip_check:
        connection.get_model('res.users').search([('id','=',0)])
    return connection

def pfm(values):
    "prepare for marshalling"
    if isinstance(values, (dict, AttrDict)):
        new_values = {}
        for k, v in values.items():
            new_values[k] = _convert(v)
        return new_values
    elif isinstance(values, IDEquality):
        return values.id or False
    elif isinstance(values, (list, tuple)):
        new_list = []
        for v in values:
            new_list.append(_convert(v))
        return type(values)(new_list)
    else:
        raise ValueError('not sure how to convert %r' % (values, ))

def _convert(value):
    if not value and isinstance(value, (str, number, bool)):
        return value
    elif isinstance(value, (date, Date)):
        return value.strftime(DEFAULT_SERVER_DATE_FORMAT)
    elif isinstance(value, (datetime, DateTime)):
        return local_to_utc(value).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
    elif isinstance(value, IDEquality):
        return value.id or False
    elif isinstance(value, SelectionEnum):
        return value.db
    elif isinstance(value, Enum):
        return value.value
    elif isinstance(value, PostalCode):
        return value.code
    elif isinstance(value, Phone):
        return value.number or False
    elif isinstance(value, (dict, AttrDict, list, tuple)):
        return pfm(value)
    elif value is None:
        return False
    else:
        return value

def dbf_field_name(name):
    if len(name) <= 10:
        return name
    names = name.split('_')
    new_name = []
    for sn in names:
        if sn in ('id', 'is', 'home'):
            continue
        new_name.append(short.get(sn, sn))
    name = '_'.join(new_name)
    if len(name) > 10:
        name = ''.join(new_name)[:10]
    return name

short = {
        'address': 'addr',
        'credit': 'cr',
        'debit': 'dr',
        'description': 'desc',
        'contact': 'cntc',
        'date': 'dt',
        'emergency': 'emrgcy',
        'employment': 'emp',
        'exemptions': 'exmpt',
        'federal': 'fed',
        'flag': 'flg',
        'identification': 'ident',
        'number': 'no',
        'parent': 'prnt',
        'pension': 'pensn',
        'plan': 'pln',
        'schedule': 'sched',
        'scheduled': 'sched',
        'scheduling': 'sched',
        'special': 'spcl',
        'state': 'st',
        'status': 'sts',
        'total': 'ttl',
        'transmitter': 'trans',
        'type': 'typ',
        }

class OpenERP(object):

    def __init__(self, host, database=None, login=None, password=None, protocol="xmlrpc", port='auto'):
        self.connection = get_connection(host, protocol, port, database, login, password)

    def __getattr__(self, model):
        setattr(self, model, self.connection.get_model(model))

DbfNameSpec = NamedTuple('DbfNameSpec', ['name', 'spec'])


# exceptions

class ErpError(Exception):
    def __init__(self, msg='', value=None):
        self.msg = msg
        self.value = value
        if self.value is None:
            self.args = (msg, )
        else:
            self.args = msg, value
    def __repr__(self):
        if self.value is None:
            return "%s(%r)" % (self.__class__.__name__, self.msg)
        else:
            return "%s(%r, value=%r)" % (self.__class__.__name__, self.msg, self.value)

class AccessDenied(ErpError):
    pass

class AccessError(ErpError):
    pass

class MissingError(ErpError):
    pass

class ValidationError(ErpError):
    pass

class ConstraintError(ErpError):
    pass
