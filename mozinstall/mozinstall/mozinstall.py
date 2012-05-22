# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import mozinfo
from optparse import OptionParser
import os
import subprocess
import sys
import tarfile
import zipfile

if mozinfo.isMac:
    from plistlib import readPlist


_default_apps = ["firefox",
                 "thunderbird",
                 "fennec"]


class InstallError(Exception):
    """
    Thrown when the installation fails. Includes traceback
    if available.
    """


class InvalidSource(Exception):
    """
    Thrown when the specified source is not a recognized
    file type (zip, exe, tar.gz, tar.bz2 or dmg)
    """


def install(src, dest=None, apps=_default_apps):
    """
    Installs a zip, exe, tar.gz, tar.bz2 or dmg file
    src - the path to the install file
    dest - the path to install to [default is os.path.dirname(src)]

    returns - the full path to the binary in the installed folder
              or None if the binary cannot be found
    """

    src = os.path.realpath(src)
    assert(os.path.isfile(src))

    if not dest:
        dest = os.path.dirname(src)

    trbk = None
    try:
        install_dir = None
        if zipfile.is_zipfile(src) or tarfile.is_tarfile(src):
            install_dir = _extract(src, dest)[0]
        elif mozinfo.isMac and src.lower().endswith(".dmg"):
            install_dir = _install_dmg(src, dest)
        elif mozinfo.isWin and os.access(src, os.X_OK):
            install_dir = _install_exe(src, dest)
        else:
            raise InvalidSource(src + " is not a recognized file type " +
                                      "(zip, exe, tar.gz, tar.bz2 or dmg)")
    except InvalidSource, e:
        raise
    except Exception, e:
        cls, exc, trbk = sys.exc_info()
        install_error = InstallError("Failed to install %s" % src)
        raise install_error.__class__, install_error, trbk
    finally:
        # trbk won't get GC'ed due to circular reference
        # http://docs.python.org/library/sys.html#sys.exc_info
        del trbk

    if install_dir:
        return get_binary(install_dir, apps=apps)


def _extract(src, dest=None, delete=False):
    """
    Takes in a tar or zip file and extracts it to dest

    If dest is not specified, extracts to os.path.dirname(src)
    If delete is set to True, deletes the bundle at path

    Returns the list of top level files that were extracted
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
                if name.endswith("/"):
                    os.makedirs(filename)
                else:
                    path = os.path.dirname(filename)
                    if not os.path.isdir(path):
                        os.makedirs(path)
                    dest = open(filename, "wb")
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

    if delete:
        os.remove(src)

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
    If dest is not specified, extracts to os.path.dirname(src)

    Returns the list of top level files that were extracted
    """

    proc = subprocess.Popen("hdiutil attach " + src,
                            shell=True,
                            stdout=subprocess.PIPE)

    try:
        for data in proc.communicate()[0].split():
            if data.find("/Volumes/") != -1:
                appDir = data
                break

        for appFile in os.listdir(appDir):
            if appFile.endswith(".app"):
                appName = appFile
                break

        dest = os.path.join(dest, appName)
        assert not os.path.isfile(dest)

        if not os.path.isdir(dest):
            os.makedirs(dest)

        subprocess.call("cp -r " +
                        os.path.join(appDir, appName, "*") + " " + dest,
                        shell=True)
    finally:
        subprocess.call("hdiutil detach " + appDir + " -quiet",
                        shell=True)

    return dest


def _install_exe(src, dest):
    # possibly gets around UAC in vista (still need to run as administrator)

    os.environ['__compat_layer'] = "RunAsInvoker"
    cmd = [src, "/S", "/D=" + os.path.realpath(dest)]
    # check_call?
    subprocess.call(cmd)

    return dest


def get_binary(path, apps=_default_apps):
    """
    Finds the binary in the specified path
    path - the path within which to search for the binary

    returns - the full path to the binary in the folder
              or None if the binary cannot be found
    """

    # On OS X we can get the real binary from the app bundle
    if mozinfo.isMac:
        plist = '%s/Contents/Info.plist' % path
        assert os.path.isfile(plist), '"%s" has not been found.' % plist

        return os.path.join(path, "Contents/MacOS/",
                            readPlist(plist)['CFBundleExecutable'])

    if mozinfo.isWin:
        apps = [app + ".exe" for app in apps]

    for root, dirs, files in os.walk(path):
        for filename in files:
            # os.access evaluates to False for some reason, so not using it
            if filename in apps:
                return os.path.realpath(os.path.join(root, filename))


def cli(argv=sys.argv[1:]):
    parser = OptionParser()
    parser.add_option("-s", "--source",
                      dest="src",
                      help="Path to installation file. "
                           "Accepts: zip, exe, tar.bz2, tar.gz, and dmg")
    parser.add_option("-d", "--destination",
                      dest="dest",
                      default=None,
                      help="[optional] Directory to install application into")
    parser.add_option("--app", dest="app",
                      action="append",
                      default=_default_apps,
                      help="[optional] Application being installed. "
                           "Should be lowercase, e.g: "
                           "firefox, fennec, thunderbird, etc.")

    (options, args) = parser.parse_args(argv)
    if not options.src or not os.path.exists(options.src):
        parser.error("Error: A valid source has to be specified.")

    # Run it
    if os.path.isdir(options.src):
        binary = get_binary(options.src, apps=options.app)
    else:
        binary = install(options.src, dest=options.dest, apps=options.app)

    print binary


if __name__ == "__main__":
    sys.exit(cli())
