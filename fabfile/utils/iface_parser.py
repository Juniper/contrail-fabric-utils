#! /usr/bin/python2.7
# Copyright (c) 2016 Netronome Systems, Inc. All rights reserved.

import copy

class IfaceParser():

    iface_path = None
    iface_content = []

    def __init__(self, iface_path="/etc/network/interfaces"):
        self.read_ifaces(iface_path)


    def read_ifaces(self, iface_path="/etc/network/interfaces"):
        self.iface_path = iface_path
        with open(self.iface_path) as f:
            self.iface_content = f.readlines()


    def write_ifaces(self, iface_path=None):
        if not iface_path:
            # write to last read_ifaces path
            iface_path = self.iface_path

        with open(iface_path, 'w') as f:
            f.writelines(self.iface_content)


    def has_iface(self, name):
        match = "iface %s" % name
        for l in self.iface_content:
            if l.startswith(match):
                return True
        return False


    def is_iface_auto(self, name):
        if not self.has_iface(name):
            return False

        match = "auto %s" % name
        for l in self.iface_content:
            if l.startswith(match):
                return True
        return False


    def _iface_start_idx(self, name):
        start_idx = None
        start_match = "iface %s" % name

        last_iface_idx = None
        for i, l in enumerate(self.iface_content):
            if start_idx is None:
                if l.startswith(start_match):
                    # found iface line
                    if self.is_iface_auto(name):
                        start_idx = i-1  # Assuming auto is line immediately prior to iface
                    else:
                        start_idx = i

                    # process backwards to pick up comments
                    for j in range(start_idx-1, -1, -1):
                        if not self.iface_content[j].startswith('#'):
                            start_idx = j+1
                            break

                    break  # found iface
        return start_idx


    def _iface_end_idx(self, name):
        iface_order = self.get_iface_order()
        if name in iface_order:
            iface_idx = iface_order.index(name)
        else:
            return None

        end_idx = None

        if (iface_idx + 1) <= (len(iface_order) -1):
            next_iface_name = iface_order[iface_idx + 1]          
            end_idx = (self._iface_start_idx(iface_order[iface_idx + 1]) - 1) 
        else:
            end_idx = len(self.iface_content) -1

        return end_idx
        

    def iface_start_end_line_idx(self, name):
        start_idx = self._iface_start_idx(name)
        end_idx = self._iface_end_idx(name)

        return (start_idx, end_idx)


    def get_iface_order(self):
        iface_names = []
        for l in self.iface_content:
            if l.startswith("iface"):
                iface_names.append(l.split(' ')[1])

        return iface_names

       
    def print_iface_content(self):
        for l in self.iface_content:
            print l.rstrip('\n')


    def get_iface_lines(self, name):
        iface = []
        (start, end) = self.iface_start_end_line_idx(name)
        if start and end:
            if len(self.iface_content) - 1 >= end:
                end = end + 1  # adjust to include end line
            iface = self.iface_content[start:end]

        return iface


    def replace_iface_lines(self, name, lines):
        (start, end) = self.iface_start_end_line_idx(name)
        if start and end:
            if len(self.iface_content) -1 >= end:
                end = end + 1 # adjust to include end line
            del self.iface_content[start:end]
            self.iface_content[start:start] = lines


    def remove_iface(self, name):
        self.replace_iface_lines(name, [])


    def create_iface_auto_manual(self, name):
        new_iface_lines = []
        new_iface_lines.append("auto %s\n" % name)
        new_iface_lines.append("iface %s inet manual\n" % name)
        new_iface_lines.append("\n")

        return new_iface_lines


    def insert_iface_after(self, iface_lines, name):
        iface_order = self.get_iface_order()
        if iface_order.index(name) == (len(iface_order) - 1):
            last_line = len(self.iface_content) - 1
            self.iface_content[last_line:last_line] = iface_lines
        else:
            (s, e) = self.iface_start_end_line_idx(name)
            self.iface_content[e+1:e+1] = iface_lines
                     

    def insert_iface_before(self, iface_lines, name):
        iface_order = self.get_iface_order()
        if iface_order.index(name) == 0:
            self.iface_content[0:0] = iface_lines
        else:
            (s, e) = self.iface_start_end_line_idx(name)
            self.iface_content[s:s] = iface_lines


    def iface_add_value(self, iface_lines, value):
        val_line = "    %s" % value
        if not val_line in iface_lines:  # avoid duplicates
            insert_idx = len(iface_lines) - 1
            for l in iface_lines:
                if l.startswith("iface"):
                    insert_idx = iface_lines.index(l) + 1
                    break

            iface_lines.insert(insert_idx, val_line)
        return iface_lines


    def iface_del_value(self, iface_lines, value):
        val_line = "    %s" % value
        if val_line in iface_lines:
            iface_lines.remove(val_line)
        return iface_lines


    def clean_extra_lines(self):
        to_remove = []
        tmp_iface_content = []
        max_idx = (len(self.iface_content) - 1)
        for i, l in enumerate(self.iface_content):
            if self.iface_content[i] in ['\n', '\r\n']:
                if (i + 1) <= max_idx and (i + 1) not in to_remove:
                    if self.iface_content[i+1] in ['\n', '\r\n']:
                      to_remove.append(i+1)

        for i, l in enumerate(self.iface_content):
            if not i in to_remove:
                tmp_iface_content.append(l)

        self.iface_content = copy.deepcopy(tmp_iface_content)


