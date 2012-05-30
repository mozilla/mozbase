#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import mozinfo
from optparse import OptionParser
import os
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile

if mozinfo.isMac:
    from plistlib import readPlist


DEFAULT_APPS = ['firefox',
                'thunderbird',
                'fennec']

TIMEOUT_UNINSTALL = 60


class InstallError(Exception):
    """
    Thrown when the installation fails. Includes traceback
    if available.
    """


class InvalidBinary(Exception):
    """
    Thrown when the binary cannot be found after the installation.
    """


class InvalidSource(Exception):
    """
    Thrown when the specified source is not a recognized
    file type (zip, exe, tar.gz, tar.bz2 or dmg)
    """


class UninstallError(Exception):
    """
    Thrown when the uninstallation fails. Includes traceback
    if available.
    """


def install(src, dest=None, apps=DEFAULT_APPS):
    """
    Installs a zip, exe, tar.gz, tar.bz2 or dmg file

    src - the path to the install file
    dest - the path to install to [default is os.path.dirname(src)]
    returns - the full path to the binary in the installed folder
              or None if the binary cannot be found
    """

    src = os.path.realpath(src)
    if not is_installer(src):
        raise InvalidSource(src + ' is not a recognized file type ' +
                                  '(zip, exe, tar.gz, tar.bz2 or dmg)')

    if not dest:
        dest = os.path.dirname(src)

        # On Windows the installer doesn't create a sub folder in the
        # destination folder and would clutter the source folder
        if mozinfo.isWin and src.lower().endswith('.exe'):
            filename = os.path.splitext(os.path.basename(src))[0]
            dest = os.path.join(dest, filename)

    trbk = None
    try:
        install_dir = None
        if zipfile.is_zipfile(src) or tarfile.is_tarfile(src):
            install_dir = _extract(src, dest)[0]
        elif src.lower().endswith('.dmg'):
            install_dir = _install_dmg(src, dest)
        elif src.lower().endswith('.exe'):
            install_dir = _install_exe(src, dest)

    except Exception, e:
        cls, exc, trbk = sys.exc_info()
        error = InstallError('Failed to install %s' % src)
        raise error.__class__, error, trbk

    finally:
        # trbk won't get GC'ed due to circular reference
        # http://docs.python.org/library/sys.html#sys.exc_info
        del trbk

    if install_dir:
        return get_binary(install_dir, apps=apps)


def is_installer(src):
    """
    Tests if the given file is a valid installer package (zip, exe, tar.gz,
    tar.bz2 or dmg)

    src - the path to the install file
    """

    src = os.path.realpath(src)
    assert os.path.isfile(src), 'Installer has to be a file'

    if mozinfo.isLinux:
        return tarfile.is_tarfile(src)
    elif mozinfo.isMac:
        return src.lower().endswith('.dmg')
    elif mozinfo.isWin:
        return src.lower().endswith('.exe') or zipfile.is_zipfile(src)


def uninstall(binary):
    """
    Uninstalls the specified binary. If it has been installed via the installer
    on Windows it will make use of the uninstaller.

    binary - the path to the binary
    """

    binary = os.path.realpath(binary)
    assert os.path.isfile(binary), 'binary "%s" has to be a file.' % binary

    # We know that the binary is a file. So we can savely remove the parent
    # folder. On OS X we have to get the .app bundle.
    folder = os.path.dirname(binary)
    if mozinfo.isMac:
        folder = os.path.dirname(os.path.dirname(folder))

    # On Windows we have to use the uninstaller. If it's not available fallback
    # to the directory removal code
    if mozinfo.isWin:
        uninstall_folder = "%s\uninstall" % folder
        log_file = "%s\uninstall.log" % uninstall_folder

        if os.path.isfile(log_file):
            trbk = None
            try:
                cmdArgs = ["%s\uninstall\helper.exe" % folder, "/S"]
                result = subprocess.call(cmdArgs)
                if not result is 0:
                    raise Exception('Execution of uninstaller failed.')

                # The uninstaller spawns another process so the subprocess call
                # returns immediately. We have to wait until the uninstall
                # folder has been removed or until we run into a timeout.
                end_time = time.time() + TIMEOUT_UNINSTALL
                while os.path.exists(uninstall_folder):
                    time.sleep(1)

                    if time.time() > end_time:
                        raise Exception('Failure in removing uninstall folder.')

            except Exception, e:
                cls, exc, trbk = sys.exc_info()
                error = UninstallError('Failed to uninstall %s' % binary)
                raise error.__class__, error, trbk

            finally:
                # trbk won't get GC'ed due to circular reference
                # http://docs.python.org/library/sys.html#sys.exc_info
                del trbk

    # Ensure that we remove any trace of the installation. Even the uninstaller
    # on Windows leaves files behind we have to explicitely remove.
    shutil.rmtree(folder)


def _extract(src, dest=None):
    """
    Takes in a tar or zip file and extracts it to dest

    src - archive which has to be extracted
    dest - the path to extract to [default is os.path.dirname(src)]

    Returns the application directory
    """

    assert not os.path.isfile(dest), "dest cannot be a file"

    if dest is None:
        dest = os.path.dirname(src)
    elif not os.path.isdir(dest):
        os.makedirs(dest)

    if zipfile.is_zipfile(src):
        bundle = zipfile.ZipFile(src)
        namelist = bundle.namelist()

        if hasattr(bundle, 'extractall'):
            # zipfile.extractall doesn't exist in Python 2.5
            bundle.extractall(path=dest)
        else:
            for name in namelist:
                filename = os.path.realpath(os.path.join(dest, name))
                if name.endswith('/'):
                    os.makedirs(filename)
                else:
                    path = os.path.dirname(filename)
                    if not os.path.isdir(path):
                        os.makedirs(path)
                    dest = open(filename, 'wb')
                    dest.write(bundle.read(name))
                    dest.close()

    elif tarfile.is_tarfile(src):
        bundle = tarfile.open(src)
        namelist = bundle.getnames()

        if hasattr(bundle, 'extractall'):
            # tarfile.extractall doesn't exist in Python 2.4
            bundle.extractall(path=dest)
        else:
            for name in namelist:
                bundle.extract(name, path=dest)
    else:
        return

    bundle.close()

    # namelist returns paths with forward slashes even in windows
    top_level_files = [os.path.join(dest, name) for name in namelist
                             if len(name.rstrip('/').split('/')) == 1]

    # namelist doesn't include folders, append these to the list
    for name in namelist:
        root = os.path.join(dest, name[:name.find('/')])
        if root not in top_level_files:
            top_level_files.append(root)

    return top_level_files


def _install_dmg(src, dest):
    """
    Takes in a dmg file and extracts it to destination folder

    src - dmg image of the application
    dest - the path to extract to [default is os.path.dirname(src)]

    Returns the application directory
    """

    try:
        proc = subprocess.Popen('hdiutil attach %s' % src,
                                shell=True,
                                stdout=subprocess.PIPE)

        for data in proc.communicate()[0].split():
            if data.find('/Volumes/') != -1:
                appDir = data
                break

        for appFile in os.listdir(appDir):
            if appFile.endswith('.app'):
                appName = appFile
                break

        mounted_path = os.path.join(appDir, appName)

        dest = os.path.join(dest, appName)
        assert not os.path.isfile(dest)

        # copytree() would fail if dest already exists.
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(mounted_path, dest, False)

    finally:
        subprocess.call('hdiutil detach %s -quiet' % appDir,
                        shell=True)

    return dest


def _install_exe(src, dest):
    """
    Takes in an exe file (installer) and silently installs the application
    into the destination folder

    src - exe installer of the application
    dest - the path to install to [default is os.path.dirname(src)]

    Returns the application directory
    """

    # possibly gets around UAC in vista (still need to run as administrator)

    os.environ['__compat_layer'] = 'RunAsInvoker'
    cmd = [src, '/S', '/D=%s' % os.path.realpath(dest)]

    # As long as we support Python 2.4 check_call will not be available.
    result = subprocess.call(cmd)
    if not result is 0:
        raise Exception('Execution of installer failed.')

    return dest


def get_binary(path, apps=DEFAULT_APPS):
    """
    Finds the binary in the specified path
    path - the path within to search for the binary

    Returns the full path to the binary in the folder or throws an
    InvalidBinary exception if the binary cannot be found
    """

    binary = None

    # On OS X we can get the real binary from the app bundle
    if mozinfo.isMac:
        plist = '%s/Contents/Info.plist' % path
        assert os.path.isfile(plist), '"%s" has not been found.' % plist

        binary = os.path.join(path, 'Contents/MacOS/',
                              readPlist(plist)['CFBundleExecutable'])

    else:
        if mozinfo.isWin:
            apps = [app + '.exe' for app in apps]

        for root, dirs, files in os.walk(path):
            for filename in files:
                # os.access evaluates to False for some reason, so not using it
                if filename in apps:
                    binary = os.path.realpath(os.path.join(root, filename))
                    break

    if not binary:
        # The expected binary has not been found. Make sure we clean the
        # install folder to remove any traces
        shutils.rmtree(path)

        raise InvalidBinary('"%s" does not contain a valid binary.' % path)

    return binary


def cli(argv=sys.argv[1:]):
    parser = OptionParser()
    parser.add_option('-s', '--source',
                      dest='src',
                      help='Path to installation file. '
                           'Accepts: zip, exe, tar.bz2, tar.gz, and dmg')
    parser.add_option('-d', '--destination',
                      dest='dest',
                      default=None,
                      help='[optional] Directory to install application into')
    parser.add_option('--app', dest='app',
                      action='append',
                      default=DEFAULT_APPS,
                      help='[optional] Application being installed. '
                           'Should be lowercase, e.g: '
                           'firefox, fennec, thunderbird, etc.')

    (options, args) = parser.parse_args(argv)
    if not options.src or not os.path.exists(options.src):
        parser.error('Error: A valid source has to be specified.')

    # Run it
    if os.path.isdir(options.src):
        binary = get_binary(options.src, apps=options.app)
    else:
        binary = install(options.src, dest=options.dest, apps=options.app)

    print binary


if __name__ == '__main__':
    sys.exit(cli())
