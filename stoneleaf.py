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
        ):
    """get records from model

    (connection, model):  (model_obj, None) or (connection, model_str)
    domain:   OpenERP domain for selecting records
    fields:   fields to retrieve (otherwise all)
    max_qty:  raises ValueError if more than max_qty records retrieved

    returns a list of all records found
    """
    if model is None:
        # connection is a model object, switch 'em
        model, connection = connection, model
    else:
        # connection is a connection
        # model is a string, get the real thing
        model = connection.get_model(model)
    # if skip_fields, build actual fields list
    if skip_fields:
        if fields:
            raise ValueError('Cannot specify both fields and skip_fields')
        fields = [f for f in model.fields_get_keys() if f not in skip_fields]
    single = False
    if ids:
        if isinstance(ids, (int,long)):
            single = True
            ids = [ids]
        result = model.search_read(domain=[('id','in',ids)], offset=offset, limit=limit, order=order, fields=fields)
        if len(result) != len(ids):
            found = set([r.id for r in result])
            missing = sorted([i for i in ids if i not in found])
            if missing:
                raise MissingRecord('missing record(s): %s' % ', '.join([str(m) for m in missing]))
    else:
        result = model.search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)
    if max_qty is not None and len(result) > max_qty:
        raise ValueError('no more than %s records expected, but received %s' % (max_qty, len(result)))
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
        else:
            res[key] = value
    return res

class AttrDict(object):
    """
    allows dictionary lookup using . notation
    allows a default similar to defaultdict
    """

    _internal = ['_illegal', '_values', '_default', '_order']
    _default = None

    def __init__(yo, *args, **kwargs):
        "kwargs is evaluated last"
        if 'default' in kwargs:
            yo._default = kwargs.pop('default')
        needs_sorted = False
        yo._values = _values = {}
        yo._order = _order = []
        yo._illegal = _illegal = tuple([attr for attr in dir(_values) if attr[0] != '_'])
        if yo._default is None:
            default_factory = lambda : False
        else:
            default_factory = yo._default
        for arg in args:
            # first, see if it's a lone string
            if isinstance(arg, basestring):
                arg = [(arg, default_factory())]
            # next, see if it's a mapping
            try:
                arg = arg.items()
                needs_sorted = True
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
                    raise ValueError('%s is a reserved word' % key)
                _values[key] = value
                if key not in _order:
                    _order.append(key)
        if kwargs:
            needs_sorted = True
            _values.update(kwargs)
            _order.extend([k for k in kwargs.keys() if k not in _order])
        if needs_sorted:
            _order.sort()

    def __contains__(yo, key):
        return key in yo._values

    def __delitem__(yo, name):
        if name[0] == '_':
            raise KeyError("illegal key name: %s" % name)
        if name not in yo._values:
            raise KeyError("%s: no such key" % name)
        yo._values.pop(name)
        yo._order.pop(yo._order.index(name))

    def __delattr__(yo, name):
        if name[0] == '_':
            raise AttributeError("illegal key name: %s" % name)
        if name not in yo._values:
            raise AttributeError("%s: no such key" % name)
        yo._values.pop(name)
        yo._order.pop(yo._order.index(name))

    def __eq__(yo, other):
        if isinstance(other, AttrDict):
            other = other._values
        elif not isinstance(other, dict):
            return NotImplemented
        return other == yo._values

    def __ne__(yo, other):
        result = yo == other
        if result is NotImplemented:
            return result
        else:
            return not result

    def __getitem__(yo, name):
        if name in yo._values:
            return yo._values[name]
        elif yo._default:
            yo._order.append(name)
            result = yo._values[name] = yo._default()
            return result
        raise KeyError("object has no key %s" % name)

    def __getattr__(yo, name):
        if name in yo._values:
            return yo._values[name]
        attr = getattr(yo._values, name, None)
        if attr is not None:
            return attr
        elif yo._default:
            yo._order.append(name)
            result = yo._values[name] = yo._default()
            return result
        raise AttributeError("object has no attribute %s" % name)

    def __iter__(yo):
        if len(yo._values) != len(yo._order):
            _order = set(yo._order)
            for key in yo._values:
                if key not in _order:
                    yo._order.append(key)
        return iter(yo._order)

    def __len__(yo):
        return len(yo._values)

    def __setitem__(yo, name, value):
        if name in yo._internal:
            object.__setattr__(yo, name, value)
        elif isinstance(name, basestring) and name[0:1] == '_':
            raise KeyError("illegal attribute name: %s" % name)
        elif not isinstance(name, basestring):
            raise ValueError('attribute names must be str, not %r' % type(name))
        else:
            if name not in yo._values:
                yo._order.append(name)
            yo._values[name] = value

    def __setattr__(yo, name, value):
        if name in yo._internal:
            object.__setattr__(yo, name, value)
        elif name[0] == '_' or name in yo._illegal:
            raise AttributeError("illegal attribute name: %s" % name)
        elif not isinstance(name, basestring):
            raise ValueError('attribute names must be str, not %r' % type(name))
        else:
            if name not in yo._values:
                yo._order.append(name)
            yo._values[name] = value

    def __repr__(yo):
        if not yo:
            return "AttrDict()"
        return "AttrDict([%s])" % ', '.join(["(%r, %r)" % (x, yo._values[x]) for x in yo])

    def __str__(yo):
        lines = ['{']
        for k, v in sorted(yo._values.items()):
            if isinstance(v, yo.__class__):
                lines.append(' %s = {' % k)
                for line in str(v).split('\n')[1:-1]:
                    lines.append('     %s' % line)
                lines.append('      }')
            else:
                lines.append(' %s = %r' % (k, v))
        lines.append(' }')
        return '\n'.join(lines)

    def keys(yo):
        return yo._order[:]

    __pop_sentinel = object()
    def pop(yo, name, default=__pop_sentinel):
        if name in yo._values:
            yo._order.pop(yo._order.index(name))
            return yo._values.pop(name)
        elif default is not yo.__pop_sentinel:
            return default
        else:
            raise KeyError('key not found: %r' % name)


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
