# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (C) 2015 Ethan Furman
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

import os as _os
import sys as _sys
import aenum as _aenum

DEFAULT_SERVER_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_SERVER_TIME_FORMAT = "%H:%M:%S"
DEFAULT_SERVER_DATETIME_FORMAT = "%s %s" % (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_TIME_FORMAT)

class MissingRecord(Exception):
    "records not found during id search"

def get_records(
        connection, model=None, domain=[(1,'=',1)], fields=[],
        offset=0, limit=None, order=None,
        max_qty=None, ids=None, skip_fields=[],
        context=None,
        ):
    """get records from model

    (connection, model):  (model_obj, None) or (connection, model_str)
    domain:   OpenERP domain for selecting records
    fields:   fields to retrieve (otherwise all)
    max_qty:  raises ValueError if more than max_qty records retrieved

    returns a list of all records found
    """
    context = context or {}
    if model is None:
        # connection is a model object, switch 'em
        model, connection = connection, model
    else:
        # connection is a connection
        # model is a string, get the real thing
        model = connection.get_model(model)
    model_fields = model.fields_get_keys()
    # if skip_fields, build actual fields list
    if skip_fields:
        if fields:
            raise ValueError('Cannot specify both fields and skip_fields')
        fields = [f for f in model_fields if f not in skip_fields]
    single = False
    if ids:
        if isinstance(ids, (int,long)):
            single = True
            ids = [ids]
        domain=[('id','in',ids)]
        if 'active' in model_fields and 'active_test' not in context:
            context['active_test'] = False
        result = model.search_read(domain=domain, offset=offset, limit=limit, order=order, fields=fields, context=context)
        if len(result) != len(ids):
            found = set([r.id for r in result])
            missing = sorted([i for i in ids if i not in found])
            if missing:
                raise MissingRecord('missing record(s): %s' % ', '.join([str(m) for m in missing]))
    else:
        result = model.search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order, context=context)
    if max_qty is not None and len(result) > max_qty:
        raise ValueError('no more than %s records expected for %r, but received %s'
                % (max_qty, ids or domain, len(result)))
    result = [_normalize(r) for r in result]
    if single:
        result = result[0]
    return result

def _normalize(d):
    'recursively convert each dict into a AttrDict'
    res = AttrDict()
    for key, value in sorted(d.items()):
        if isinstance(value, dict):
            res[key] = _normalize(value)
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

class Many2One(_aenum.NamedTuple):
    id = 0, "OpenERP id of record"
    name = 1, "_rec_name field of record"

    def __eq__(self, other):
        if isinstance(other, (int, long)):
            return self[0] == other
        elif isinstance(other, self.__class__):
            return self[0] == other[0]
        else:
            return NotImplemented

    def __ne__(self, other):
        if isinstance(other, (int, long)):
            return self[0] != other
        elif isinstance(other, self.__class__):
            return self[0] != other[0]
        else:
            return NotImplemented

class AttrDict(object):
    """
    allows dictionary lookup using . notation
    allows a default similar to defaultdict
    iterations always ordered by key
    """

    _internal = ['_illegal', '_values', '_default']
    _default = None

    def __init__(self, *args, **kwargs):
        "kwargs is evaluated last"
        if 'default' in kwargs:
            self._default = kwargs.pop('default')
        self._values = _values = {}
        self._illegal = _illegal = tuple([attr for attr in dir(_values) if attr[0] != '_'])
        if self._default is None:
            default_factory = lambda : False
        else:
            default_factory = self._default
        for arg in args:
            # first, see if it's a lone string
            if isinstance(arg, basestring):
                arg = [(arg, default_factory())]
            # next, see if it's a mapping
            try:
                arg = arg.items()
            except (AttributeError, ):
                pass
            # now iterate over it
            for item in arg:
                if isinstance(item, basestring):
                    key, value = item, default_factory()
                else:
                    key, value = item
                if not isinstance(key, basestring):
                    raise ValueError('keys must be strings, but %r is %r' % (key, type(key)))
                if key in _illegal:
                    raise ValueError('%r is a reserved word' % key)
                _values[key] = value
        if kwargs:
            _values.update(kwargs)

    def __contains__(self, key):
        return key in self._values

    def __delitem__(self, name):
        if name[0] == '_':
            raise KeyError("illegal key name: %r" % name)
        if name not in self._values:
            raise KeyError("%s: no such key" % name)
        self._values.pop(name)

    def __delattr__(self, name):
        if name[0] == '_':
            raise AttributeError("illegal key name: %r" % name)
        if name not in self._values:
            raise AttributeError("%s: no such key" % name)
        self._values.pop(name)

    def __eq__(self, other):
        if isinstance(other, AttrDict):
            other = other._values
        elif not isinstance(other, dict):
            return NotImplemented
        return other == self._values

    def __ne__(self, other):
        result = self == other
        if result is NotImplemented:
            return result
        else:
            return not result

    def __getitem__(self, name):
        if name in self._values:
            return self._values[name]
        elif self._default:
            result = self._values[name] = self._default()
            return result
        else:
            raise KeyError("object has no key %r" % name)

    def __getattr__(self, name):
        if name in self._values:
            return self._values[name]
        attr = getattr(self._values, name, None)
        if attr is not None:
            return attr
        elif self._default:
            result = self._values[name] = self._default()
            return result
        else:
            raise AttributeError("object has no attribute %r" % name)

    def __iter__(self):
        return iter(sorted(self.keys()))

    def __len__(self):
        return len(self._values)

    def __setitem__(self, name, value):
        if name in self._internal:
            object.__setattr__(self, name, value)
        elif isinstance(name, basestring) and name[0:1] == '_':
            raise KeyError("illegal attribute name: %r" % name)
        elif not isinstance(name, basestring):
            raise ValueError('attribute names must be str, not %r' % type(name))
        else:
            self._values[name] = value

    def __setattr__(self, name, value):
        if name in self._internal:
            object.__setattr__(self, name, value)
        elif name[0] == '_' or name in self._illegal:
            raise AttributeError("illegal attribute name: %r" % name)
        elif not isinstance(name, basestring):
            raise ValueError('attribute names must be str, not %r' % type(name))
        else:
            self._values[name] = value

    def __repr__(self):
        if not self:
            return "AttrDict()"
        return "AttrDict([%s])" % ', '.join(["(%r, %r)" % (k, self._values[k]) for k in self.keys()])

    def __str__(self):
        lines = ['{']
        for k, v in self.items():
            if isinstance(v, self.__class__):
                lines.append(' %s = {' % k)
                for line in str(v).split('\n')[1:-1]:
                    lines.append('     %s' % line)
                lines.append('      }')
            else:
                lines.append(' %r:  %r' % (k, v))
        lines.append(' }')
        return '\n'.join(lines)

    def keys(self):
        return sorted(self._values.keys())

    def items(self):
        return sorted(self._values.items())

    def values(self):
        return [v for k, v in sorted(self._values.items())]


class EmbeddedNewlineError(ValueError):
    "Embedded newline found in a quoted field"

    def __init__(self, state):
        super(EmbeddedNewlineError, self).__init__()
        self.state = state


class OpenERPcsv(object):
    """csv file in OE format (utf-8, "-encapsulated, comma seperated)
    returns a list of str, bool, float, and int types, one row for each record
    Note: discards first record -- make sure it is the header!"""

    def __init__(self, filename):
        with open(filename) as source:
            self.data = source.readlines()
        self.row = 0        # skip header during iteration
        header = self.header = self._convert_line(self.data[0])
        self.types = []
        known = globals()
        for name in header:
            if '%' in name:
                name, type = name.split('%')
                if type in known:
                    self.types.append(known[type])
                else:
                    func = known['__builtins__'].get(type, None)
                    if func is not None:
                        self.types.append(func)
                    else:
                        raise ValueError("unknown type: %s" % type)
            else:
                self.types.append(None)

    def __iter__(self):
        return self

    def __next__(self):     # just plain 'next' in python 2
        try:
            self.row += 1
            line = self.data[self.row]
        except IndexError:
            raise StopIteration
        items = self._convert_line(line)
        if len(self.types) != len(items):
            raise ValueError('field/header count mismatch on line: %d' % self.row)
        result = []
        for item, type in zip(items, self.types):
            if type is not None:
                result.append(type(item))
            elif item.lower() in ('true','yes','on','t','y'):
                result.append(True)
            elif item.lower() in ('false','no','off','f','n'):
                result.append(False)
            else:
                for type in (int, float, lambda s: str(s.strip('"'))):
                    try:
                        result.append(type(item))
                    except Exception:
                        pass
                    else:
                        break
                else:
                    result.append(None)
        return result
    next = __next__

    @staticmethod
    def _convert_line(line, prev_state=None):
        line = line.strip() + ','
        if prev_state:
            fields = prev_state.fields
            word = prev_state.word
            encap = prev_state.encap
            skip_next = prev_state.skip_next
        else:
            fields = []
            word = []
            encap = False
            skip_next = False
        for i, ch in enumerate(line):
            if skip_next:
                skip_next = False
                continue
            if encap:
                if ch == '"' and line[i+1:i+2] == '"':
                    word.append(ch)
                    skip_next = True
                elif ch =='"' and line[i+1:i+2] in ('', ','):
                    while word[-1] == '\\n':
                        word.pop()
                    word.append(ch)
                    encap = False
                elif ch == '"':
                    raise ValueError(
                            'invalid char following ": <%s> (should be comma or double-quote)\n%r\n%s^'
                            % (ch, line, ' ' * i)
                            )
                else:
                    word.append(ch)
            else:
                if ch == ',':
                    fields.append(''.join(word))
                    word = []
                elif ch == '"':
                    if word: # embedded " are not allowed
                        raise ValueError('embedded quotes not allowed:\n%s\n%s' % (line[:i], line))
                    encap = True
                    word.append(ch)
                else:
                    word.append(ch)
        if encap:
            word.pop()  # discard trailing comma
            if len(word) > 1:  # more than opening quote
                word[-1] = '\\n'
            current_state = AttrDict(fields=fields, word=word, encap=encap, skip_next=skip_next)
            raise EmbeddedNewlineError(state=current_state)
        return fields


class SchroedingerFile(object):
    "loops through lines of filename *if it exists*; deletes file when finished"

    filename = None
    ctxmgr = None

    def __init__(self, filename):
        try:
            self.data = open(filename)
            self.filename = filename
        except IOError:
            self.data = iter([])

    def __enter__(self):
        self.ctxmgr = True
        return self

    def __exit__(self, *args):
        if self.filename:
            try:
                _os.remove(self.filename)
            except OSError:
                pass

    def __iter__(self):
        return self

    def __next__(self):     # just plain 'next' in python 2
        try:
            return next(self.data)
        except StopIteration:
            exc = _sys.exc_info()[1]
            if self.filename and not self.ctxmgr:
                try:
                    _os.remove(self.filename)
                except OSError:
                    pass
            self.data = iter([])
            raise exc
    next = __next__
