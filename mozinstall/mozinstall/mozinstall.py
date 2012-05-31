#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

"""Module to handle the installation and uninstallation of Gecko based
applications across platforms.

"""
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
    """Thrown when installation fails. Includes traceback if available."""


class InvalidBinary(Exception):
    """Thrown when the binary cannot be found after the installation."""


class InvalidSource(Exception):
    """Thrown when the specified source is not a recognized file type.

    Supported types:
    Linux:   tar.gz, tar.bz2
    Mac:     dmg
    Windows: zip, exe

    """


class UninstallError(Exception):
    """Thrown when uninstallation fails. Includes traceback if available."""


def get_binary(path, apps=DEFAULT_APPS):
    """Find the binary in the specified path, and return its path. If binary is
    not found throw an InvalidBinary exception.

    Arguments:
    path -- the path within to search for the binary

    Keyword arguments:
    apps -- list of binaries without file extension to look for

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
        shutil.rmtree(path)

        raise InvalidBinary('"%s" does not contain a valid binary.' % path)

    return binary


def install(src, dest=None, apps=DEFAULT_APPS):
    """Install a zip, exe, tar.gz, tar.bz2 or dmg file, and return the path of
    the binary. If binary is not found throw an InstallError exception.

    Arguments:
    src  -- the path to the install file

    Keyword arguments:
    dest -- the path to install to (default: sub folder in current working dir)
    apps -- list of binaries without file extension to look for

    """
    src = os.path.realpath(src)
    if not is_installer(src):
        raise InvalidSource(src + ' is not a recognized file type ' +
                                  '(zip, exe, tar.gz, tar.bz2 or dmg)')

    if not dest:
        dest = os.getcwd()

        # On Windows the installer doesn't create a sub folder in the
        # destination folder and would clutter the current working dir
        if mozinfo.isWin and src.lower().endswith('.exe'):
            filename = os.path.basename(src).split('.')[0]
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
        error = InstallError('Failed to install "%s"' % src)
        raise InstallError, error, trbk

    finally:
        # trbk won't get GC'ed due to circular reference
        # http://docs.python.org/library/sys.html#sys.exc_info
        del trbk

    if install_dir:
        return get_binary(install_dir, apps=apps)


def is_installer(src):
    """Tests if the given file is a valid installer package.

    Supported types:
    Linux:   tar.gz, tar.bz2
    Mac:     dmg
    Windows: zip, exe

    Arguments:
    src -- the path to the install file

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
    """Uninstalls the specified binary. If it has been installed via an
    installer on Windows it will make use of the uninstaller first.

    Arguments:
    binary -- the path to the binary

    """
    binary = os.path.realpath(binary)
    assert os.path.isfile(binary), 'binary "%s" has to be a file.' % binary

    # We know that the binary is a file. So we can safely remove the parent
    # folder. On OS X we have to get the .app bundle.
    folder = os.path.dirname(binary)
    if mozinfo.isMac:
        folder = os.path.dirname(os.path.dirname(folder))

    # On Windows we have to use the uninstaller. If it's not available fallback
    # to the directory removal code
    if mozinfo.isWin:
        uninstall_folder = '%s\uninstall' % folder
        log_file = '%s\uninstall.log' % uninstall_folder

        if os.path.isfile(log_file):
            trbk = None
            try:
                cmdArgs = ['%s\uninstall\helper.exe' % folder, '/S']
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
                        raise Exception('Failure removing uninstall folder.')

            except Exception, e:
                cls, exc, trbk = sys.exc_info()
                error = UninstallError('Failed to uninstall %s' % binary)
                raise UninstallError, error, trbk

            finally:
                # trbk won't get GC'ed due to circular reference
                # http://docs.python.org/library/sys.html#sys.exc_info
                del trbk

    # Ensure that we remove any trace of the installation. Even the uninstaller
    # on Windows leaves files behind we have to explicitely remove.
    shutil.rmtree(folder)


def _extract(src, dest):
    """Extract a tar or zip file into the destination folder and return the
    application folder.

    Arguments:
    src -- archive which has to be extracted
    dest -- the path to extract to

    """

    if not os.path.exists(dest):
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


def _install_dmg(src, dest=None):
    """Extract a dmg file into the destination folder and return the
    application folder.

    Arguments:
    src -- DMG image which has to be extracted
    dest -- the path to extract to

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

        # copytree() would fail if dest already exists.
        if os.path.exists(dest):
            raise InstallError('App bundle "%s" already exists.' % dest)

        shutil.copytree(mounted_path, dest, False)

    finally:
        subprocess.call('hdiutil detach %s -quiet' % appDir,
                        shell=True)

    return dest


def _install_exe(src, dest):
    """Run the MSI installer to silently install the application into the
    destination folder. Return the folder path.

    Arguments:
    src -- MSI installer to be executed
    dest -- the path to install to

    """
    if os.path.exists(dest):
        raise InstallError('Installation directory "%s" already exists' % dest)

    # possibly gets around UAC in vista (still need to run as administrator)
    os.environ['__compat_layer'] = 'RunAsInvoker'
    cmd = [src, '/S', '/D=%s' % os.path.realpath(dest)]

    # As long as we support Python 2.4 check_call will not be available.
    result = subprocess.call(cmd)
    if not result is 0:
        raise Exception('Execution of installer failed.')

    return dest


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
