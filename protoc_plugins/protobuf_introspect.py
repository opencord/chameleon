#!/usr/bin/env python

# Copyright 2017 the original author or authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
Load a protobuf description file or protoc CodeGeneratorRequest an make
sense of it
"""

import os
import inspect
from collections import OrderedDict

import sys

from google.protobuf.compiler.plugin_pb2 import CodeGeneratorRequest
from google.protobuf.descriptor import FieldDescriptor, Descriptor
from google.protobuf.descriptor_pb2 import FileDescriptorProto, MethodOptions
from google.protobuf.message import Message, DecodeError
from simplejson import dumps

from google.protobuf import descriptor_pb2


class InvalidDescriptorError(Exception): pass


class DescriptorParser(object):

    def __init__(self, ignore_empty_source_code_info=True):
        self.ignore_empty_source_code_info = ignore_empty_source_code_info
        self.catalog = {}
        self.meta, blob = self.load_root_descriptor()
        self.load_descriptor(blob)

    def load_root_descriptor(self):
        """Load descriptor.desc to make things more data driven"""
        with open('descriptor.desc', 'r') as f:
            blob = f.read()
        proto = descriptor_pb2.FileDescriptorSet()
        proto.ParseFromString(blob)
        assert len(proto.file) == 1
        fdp = proto.file[0]

        # for i, (fd, v) in enumerate(fdp.ListFields()):
        #     assert isinstance(fd, FieldDescriptor)
        #     print fd.name, fd.full_name, fd.number, fd.type, fd.label, fd.message_type, type(v)

        return fdp, blob

    def get_catalog(self):
        return self.catalog

    def load_descriptor(self, descriptor_blob,
                        fold_comments=True,
                        type_tag_name='_type'):

        # decode file descriptor set or if that is not possible,
        # try plugin request
        try:
            message = descriptor_pb2.FileDescriptorSet()
            message.ParseFromString(descriptor_blob)
        except DecodeError:
            message = CodeGeneratorRequest()
            message.ParseFromString(descriptor_blob)

        d = self.parse(message, type_tag_name=type_tag_name)
        print d.keys()
        for _file in d.get('file', None) or d['proto_file']:
            if fold_comments:
                self.fold_comments_in(_file)
            self.catalog[_file['package']] = _file

    def parse_message(self, m, type_tag_name=None):
        assert isinstance(m, Message)
        d = OrderedDict()
        for fd, v in m.ListFields():
            assert isinstance(fd, FieldDescriptor)
            if fd.label in (1, 2):
                d[fd.name] = self.parse(v, type_tag_name)
            elif fd.label == 3:
                d[fd.name] = [self.parse(x, type_tag_name) for x in v]
            else:
                raise InvalidDescriptorError()

        if type_tag_name is not None:
            d[type_tag_name] = m.DESCRIPTOR.full_name

        return d

    parser_table = {
        unicode: lambda x: x,
        int: lambda x: x,
        bool: lambda x: x,
    }

    def parse(self, o, type_tag_name=None):
        if isinstance(o, Message):
            return self.parse_message(o, type_tag_name)
        else:
            return self.parser_table[type(o)](o)

    def fold_comments_in(self, descriptor):
        assert isinstance(descriptor, dict)

        locations = descriptor.get('source_code_info', {}).get('location', [])
        for location in locations:
            path = location.get('path', [])
            comments = ''.join([
                location.get('leading_comments', '').strip(' '),
                location.get('trailing_comments', '').strip(' '),
                ''.join(block.strip(' ') for block
                          in location.get('leading_detached_comments', ''))
            ]).strip()

            # ignore locations with no comments
            if not comments:
                continue

            # we ignore path with odd number of entries, since these do
            # not address our schema nodes, but rather the meta schema
            if (len(path) % 2 == 0):
                node = self.find_node_by_path(
                    path, self.meta.DESCRIPTOR, descriptor)
                assert isinstance(node, dict)
                node['_description'] = comments

        # remove source_code_info
        del descriptor['source_code_info']

    def find_node_by_path(self, path, meta, o):

        # stop recursion when path is empty
        if not path:
            return o

        # sanity check
        assert len(path) >= 2
        assert isinstance(meta, Descriptor)
        assert isinstance(o, dict)

        # find field name, then actual field
        field_number = path.pop(0)
        field_def = meta.fields_by_number[field_number]
        field = o[field_def.name]

        # field must be a list, extract entry with given index
        assert isinstance(field, list)  # expected to be a list field
        index = path.pop(0)
        child_o = field[index]

        child_meta = field_def.message_type
        return self.find_node_by_path(path, child_meta, child_o)


if __name__ == '__main__':

    # try loading voltha descriptor and turn it into JSON data as a preparation
    # for generating JSON Schema / swagger file (to be done later)
    if len(sys.argv) >= 2:
        desc_file = sys.argv[1]
    else:
        desc_dir = os.path.dirname(inspect.getfile(voltha_pb2))
        desc_file = os.path.join(desc_dir, 'voltha.desc')

    from voltha.protos import voltha_pb2
    with open(desc_file, 'rb') as f:
        descriptor_blob = f.read()

    parser = DescriptorParser()
    parser.save_file_desc = '/tmp/grpc_introspection.out'

    parser.load_descriptor(descriptor_blob)
    print dumps(parser.get_catalog(), indent=4)
    sys.exit(0)

    # try to see if we can decode binary data into JSON automatically
    from random import seed, randint
    seed(0)

    def make_mc(name, n_children=0):
        mc = voltha_pb2.MoreComplex(
            name=name,
            foo_counter=randint(0, 10000),
            health=voltha_pb2.HealthStatus(
                state=voltha_pb2.HealthStatus.OVERLOADED
            ),
            address=voltha_pb2.Address(
                street='1383 N McDowell Blvd',
                city='Petaluma',
                zip=94954,
                state='CA'
            ),
            children=[make_mc('child%d' % (i + 1)) for i in xrange(n_children)]
        )
        return mc

    mc = make_mc('root', 3)
    blob = mc.SerializeToString()
    print len(blob), 'bytes'
    mc2 = voltha_pb2.MoreComplex()
    mc2.ParseFromString(blob)
    assert mc == mc2

    print dumps(parser.parse(mc, type_tag_name='_type'), indent=4)
