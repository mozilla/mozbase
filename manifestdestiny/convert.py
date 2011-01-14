#!/usr/bin/env python

# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
# 
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
# 
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
# 
# The Original Code is mozilla.org code.
# 
# The Initial Developer of the Original Code is
# Mozilla.org.
# Portions created by the Initial Developer are Copyright (C) 2010
# the Initial Developer. All Rights Reserved.
# 
# Contributor(s):
#     Jeff Hammel <jhammel@mozilla.com>     (Original author)
# 
# Alternatively, the contents of this file may be used under the terms of
# either of the GNU General Public License Version 2 or later (the "GPL"),
# or the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
# 
# ***** END LICENSE BLOCK *****
"""
convert a directory to a simple manifest
"""


import os
import sys
from fnmatch import fnmatch
from optparse import OptionParser

def convert(directories, pattern=None, ignore=(), write=None):
  retval = []
  include = []
  for directory in directories:
    for dirpath, dirnames, filenames in os.walk(directory):

      # filter out directory names
      dirnames = [ i for i in dirnames if i not in ignore ]

      # reference only the subdirectory
      _dirpath = dirpath
      dirpath = dirpath.split(directory, 1)[-1].strip('/')

      if dirpath.split(os.path.sep)[0] in ignore:
        continue

      # filter by glob
      if pattern:
        filenames = [filename for filename in filenames
                     if fnmatch(filename, pattern)]

      filenames.sort()

      # write a manifest for each directory
      if write and (dirnames or filenames):
        manifest = file(os.path.join(_dirpath, write), 'w')
        for dirname in dirnames:
          print >> manifest, '[include:%s]' % os.path.join(dirname, write)
        for filename in filenames:
          print >> manifest, '[%s]' % filename
        manifest.close()

      # add to the list
      retval.extend([os.path.join(dirpath, filename)
                     for filename in filenames])

  if write:
    return # the manifests have already been written!
  
  retval.sort()
  retval = ['[%s]' % filename for filename in retval]
  return '\n'.join(retval)

def main(args=sys.argv[1:]):
  usage = '%prog [options] directory <directory> <...>'
  parser = OptionParser(usage=usage)
  parser.add_option('-p', '--pattern', dest='pattern',
                    help="glob pattern for files")
  parser.add_option('-i', '--ignore', dest='ignore',
                    default=[], action='append',
                    help='directories to ignore')
  parser.add_option('-w', '--in-place', dest='in_place',
                    help='Write .ini files in place; filename to write to')
  options, args = parser.parse_args(args)
  if not len(args):
    parser.print_usage()
    parser.exit()
  for arg in args:
    assert os.path.exists(arg)
    assert os.path.isdir(arg)
  manifest = convert(args, pattern=options.pattern, ignore=options.ignore,
                     write=options.in_place)
  if manifest:
    print manifest

if __name__ == '__main__':
  main()
