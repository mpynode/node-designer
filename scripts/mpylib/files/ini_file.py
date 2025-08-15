"""
Author: Gene Hansen

This module contains the class IniFile, which can be used to read/write data to/from ini files.
The IniFile class is a dictionary like object that is intialized off an existing .ini file or
a blank instance can be created. The keys of the this dictionary like object are the section
names within the ini file. The value within the section is also a dictionary that contains
the properties of that section as key/value pairs.

This class is built on configparser, so it requires that the contents of the ini file be grouped
into sections.

The IninFile class allows ini files to be included within other ini files by using the syntax
"#include ini_file". The importing of #included files is recursive and the contents of the
those files are merged into the final dictionary object. When using the #include keyword, the given
ini file name is treated as a relative path from the base directory of the file with the
#include call.

::

    #include my_ini
        #include ../my_stuff
        #include ./folder_name/more_stuff.ini

        [section_name]
        property_name = 2345

::

    ini_file = IniFile("C:/temp/my_file.ini")
    val = ini_file["section_name"]["property_name"]

"""

import copy
import os
from collections import OrderedDict

try:
    import configparser

    unicode = str
except:
    import ConfigParser as configparser


class IniFile(object):
    """
    :purpose:	Creates a dictionary like object to access the contents of ini files. The keys
                        of the object are the section names within the ini file.
    """

    INCLUDE_TOKEN = "#include "
    FILE_EXT = "ini"

    HEADER_SPACING = "\n"
    SECTION_SPACING = "\n\n"

    def __init__(self, ini_path=None, src_dict=None, use_includes=True, str_vals=False):
        """
        Initialize a new IniFile from an existing file on disk or create new blank IniFile instance

        **ini_path**	 	optinal *string* path to an ini file or None to make a blank IniFile
        **src_dict**	 	optional existing *dict* or 8OrderedDict* to intialize from
        **use_includes**	*bool* - True, look for and use #inlcude tags. False, do not
        **str_vals**		*bool* - return all option values as *strings*. By default, when option values are read
                                                in from an ini file, the incoming string value will be pushed through eval()
                            to convert it to its original value type. Inversely, values are formatted appropriately
                            when written to file. Setting this to True, will read/write values to/from files
                            as *strings*

        **RETURNS**			None

        """

        if src_dict:
            if type(src_dict) == dict:
                src_dict = self._convertToOrdered(src_dict)

            elif type(src_dict) != OrderedDict:
                raise TypeError(
                    "src_dict must be dict or OrderedDict. Type "
                    + str(type(src_dict))
                    + " given"
                )

        self._data = OrderedDict() if not src_dict else self._deepCopy(src_dict)
        self._ini_path = ini_path
        self._use_includes = use_includes
        self._str_vals = str_vals

        ##---protects against circular include dependencies----##
        self._used_includes = []

        if self._ini_path:
            if os.path.exists(self._ini_path):
                self._ini_path = os.path.normpath(self._ini_path).replace("\\", "/")
                self._read(self._ini_path)

            else:
                raise RuntimeError("File does not exist: " + str(self._ini_path))

    def __contains__(self, k):
        """
        :purpose:	Built-in method. Test for the presence of section name in the IniFile.
        :returns:	bool
        """
        return k in self._data

    def _deepCopy(self, src_dict):
        """
        For overriding purposes. Base class simply uses copy.deepcopy() on the src_dict that was passed into __init__.
        deepcopy() may not be safe on more complex classes.
        """

        if type(src_dict) is OrderedDict:
            return src_dict.copy()

        return copy.deepcopy(src_dict)

    def _convertToOrdered(self, ini_data):
        """
        Converts all regular dictionaries within the given ini data to OrderedDict
        """

        if type(ini_data) != OrderedDict:
            ini_data = OrderedDict(ini_data.items())

        for sect in ini_data.keys():
            if type(ini_data[sect]) == dict:
                ini_data[sect] = OrderedDict(ini_data[section].items())

            elif type(ini_data[sect]) != OrderedDict:
                raise TypeError(
                    "Section data must be type dict or OrderedDict. Type "
                    + str(type(ini_data))
                    + " found."
                )

        return ini_data

    def write(self, out_path, sect_spaces=True, opt_spaces=True):
        """
        :purpose:	Write the contents of this IniFile instance to a given file path.
        :arg		out_path: string path to export to
        :arg		sect_spaces: boolean whether to put a blank line between sections
        :arg		opt_spaces: boolean whether to put blank space on either side of the "="
                    sign between options and values
        :returns:	None
        """

        file_handle = open(out_path, "w")

        file_handle.write(self.HEADER_SPACING)

        for section in self._data.keys():
            file_handle.write("[" + str(section) + "]\n")

            options = self._data[section]

            for option in options.keys():
                value = self[section][option]

                eq_str = " = " if opt_spaces else "="

                if (not self._str_vals) and (type(value) in (str, unicode)):
                    value = '"' + str(value) + '"'

                self._writeVarString(file_handle, eq_str, option, value)

            if sect_spaces:
                file_handle.write(self.SECTION_SPACING)

        file_handle.close()

        ##----store the out path as the current file location of this object---##
        self._ini_path = os.path.normpath(out_path).replace("\\", "/")

    def _writeVarString(self, file_handle, eq_str, option, value):
        """
        Isolatates the writting of given variable/value for overriding purposes.
        """

        file_handle.write(str(option) + eq_str + str(value) + "\n")

    def _getIncludes(self, cur_path):
        """
        PRIVATE METHOD: Finds and returns the values of the #include tag within the given ini file.
        Includes should be relative paths, so this function resolves the includes relative path with
        the path of the given .ini file.
        """

        includes = []
        self._used_includes.append(cur_path)
        dirname = os.path.dirname(cur_path) + "/"

        fh = open(cur_path, "r")

        # for line in fh.xreadlines():
        for line in fh.readlines():
            line = line.strip()

            if line.startswith(self.INCLUDE_TOKEN):
                tokens = line.split()

                for basename in tokens[1:]:
                    if not basename.endswith("." + self.FILE_EXT):
                        basename += "." + self.FILE_EXT

                    path = os.path.join(dirname, basename)
                    path = os.path.normpath(path).replace("\\", "/")
                    includes.append(path)

        fh.close()

        return includes

    def _readIni(self, ini_path):
        """
        PRIVATE METHOD: Read the contents of the given ini file without worrying about includes
        """

        ini = configparser.SafeConfigParser()
        ini.optionxform = str  # keep the caseconfigparserions and values

        ini.read(ini_path)

        for section in ini.sections():
            values = ini.items(section)

            # if not self._data.has_key(section):
            if not section in self._data:
                self._data[section] = OrderedDict()

            for value in values:
                opt_val = value[1] if self._str_vals else eval(value[1])

                self._data[section][value[0]] = opt_val

    def _read(self, ini_path):
        """
        PRIVATE METHOD: Recursive method that reads all ini files included with #include
        """

        if self._use_includes:
            cur_includes = self._getIncludes(ini_path)

            for include in cur_includes:
                if not include in self._used_includes:
                    if os.path.exists(include):
                        self._read(include)
                    else:
                        raise IOError("Could not locate file: " + str(include))

        self._readIni(ini_path)

    def __getitem__(self, key):
        """
        :purpose: 	Built-in method. Allows use of dictionary syntax to get values.
                                Example -> val = ini["sect"]["var"]
        :returns:	Returns the value of the given section
        """

        return self._data[key]

    def __delitem__(self, key):
        """
        :purpose: 	Built-in method. Allows use of dictionary syntax to delete values.
                                Example -> del(ini["sect"])
        :returns:	None
        """

        del self._data[key]

    def __len__(self):
        """
        :purpose: 	Built-in method. Returns the number of sections in the IniFile and allows
                                use of len() function
                                Example -> len(ini)
        :returns:	int
        """

        return len(self._data)

    def __setitem__(self, key, value):
        """
        :purpose: 	Built-in method. Allows use of dictionary syntax to set values.
                                Example -> ini["sect"]["var"] = "val"
        :returns:	None
        """

        if type(value) != OrderedDict:
            if type(value) == dict:
                value = OrderedDict(value.items())

            else:
                raise TypeError(
                    "Sections values must be type dict or OrderedDict. Type "
                    + str(type(value))
                    + " given."
                )

        self._data[key] = value

    def __str__(self):
        """
        :purpose:	Built-in method. Handles conversion of this object's data to a string.
        :returns:	str
        """

        return str(self._data)

    def __repr__(self):
        """
        :purpose:	Built-in method. Handles conversion of this object to a string.
        :returns:	str
        """

        return str(self)

    def clear(self):
        """
        :purpose:	Built-in method. Clears all data from this IniFile instance.
        :returns:	None
        """

        return self._data.clear()

    def copy(self):
        """
        :purpose:	Built-in method. Creates a dictionary copy of this IniFile instance.
        :returns:	dictionary
        """

        return self._data.copy()

    def get(self, k, d=None):
        """
        :purpose:	Built-in method. Return the value for key if key is in the IniFile,
                                else default. If default is not given, it defaults to None, so that this method
                    never raises a KeyError.
        :returns:	value of k
        """

        return self._data.get(k, d=d)

    def has_key(self, k):
        """
        :purpose:	Built-in method. Test for the presence of section name in the IniFile.
        :returns:	bool
        """

        # return self._data.has_key(k)
        return k in self._data

    def items(self):
        return self._data.items()

    def iteritems(self):
        """
        :purpose:	Built-in method. Return an iterator over the IniFiles's (section, value) pairs.
        :returns:	iterator of a tuple of string sections names and tuple of section value dictionaries.
        """

        return self._data.iteritems()

    def iterkeys(self):
        """
        :purpose:	Built-in method. Return an iterator over the IniFiles's section names.
        :returns:	iterator of string section names
        """

        return self._data.iterkeys()

    def itervalues(self, arg):
        """
        :purpose:	Built-in method. Return an iterator over the IniFiles's section value dictionaries.
        :returns:	iterator of section value dictionaries
        """

        return self._data.itervalues()

    def keys(self):
        """
        :purpose:	Built-in method. Return a copy of the IniFiles's list of section names
        :returns:	list of string section names
        """

        return self._data.keys()

    def pop(self, k, d=None):
        """
        :purpose:	Built-in method. If k is a section in the IniFile, remove it and return its
                                value, else return default.
                                If default is not given and k is not in the IniFile, a KeyError is raised.
        :returns:	dictionary of ini section values
        """

        return self._data.pop(k, d=d)

    def popitem(self):
        """
        Built-in method. Remove and return an arbitrary (section, value) pair from the IniFile.

        :returns: tuple of tuple of string section names and section value dictionaries
        """

        return self._data.popitem()

    def setdefault(self, k, d=None):
        """
        Built-in method. If k is a section name in the IniFile, return its value. If not, insert k
        section name with a value of default and return default.

        **RETURNS**		section value dictionary or the value of d

        """

        # if self.has_key(k):
        if k in self:
            return self[k]

        elif not d is None:
            self[k] = d
            return d

        self[k] = OrderedDict()
        return self[k]

    def values(self):
        """
        :purpose:	Built-in method. Return a copy of the IniFile's list of value dictionaries.
        :returns:	list of section value dictionaries
        """

        return self._data.values()

    def asDict(self):
        """
        :purpose:	Returns the IniFile as a standard dictionary
        :returns:	dict
        """

        return dict(self._data)

    def asOrderedDict(self):
        """
        :purpose:	Returns the IniFile as a OrderedDict
        :returns:	OrderedDict
        """

        return self._data
