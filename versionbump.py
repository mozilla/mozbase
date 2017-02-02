#!/usr/bin/env python

"""bump mozbase versions"""

import optparse
import os
import pkg_resources
import re
import subprocess
import sys
import xmlrpclib

# import setup_development.py from the same directory
import setup_development

here = setup_development.here
REPOSITORY_URL = 'git@github.com:mozilla/mozbase.git'
REPOSITORY_PULL_URL = 'git://github.com/mozilla/mozbase.git'

class CalledProcessError(Exception):
    """error for bad calls"""


def format_version(**dep):
    """formats a dependency version"""
    return '%(Name)s %(Type)s %(Version)s' % dep


def call(cmd, **kwargs):
    print "Running %s, %s" % (cmd, kwargs)

    if dry_run:
        return
    kwargs.setdefault('stdout', subprocess.PIPE)
    kwargs.setdefault('stderr', subprocess.PIPE)
    process = subprocess.Popen(cmd, **kwargs)
    stdout, stderr = process.communicate()
    if process.returncode:
        print 'stdout:'
        print stdout
        print 'stderr:'
        print stderr
        raise CalledProcessError("Error running %s: %d" % (cmd,
                                                           process.returncode))


def revert(git):
    """revert the repository on error"""
    call([git, 'reset', '--hard', 'HEAD'])


def main(args=sys.argv[1:]):

    # parse command line options
    usage = '%prog [options] packageA=0.1.2 <packageB=1.2> <...>'
    parser = optparse.OptionParser(usage=usage, description=__doc__)
    parser.add_option('--info', dest='info',
                      action='store_true', default=False,
                      help="display package version information and exit")
    parser.add_option('--dry-run', dest='dry_run',
                      action='store_true', default=False,
                      help="don't make changes, just display what will be run")
    parser.add_option('--diff', dest='diff',
                      help="output the diff to this file ('-' for stdout)")
    parser.add_option('-m', '--message', dest='message',
                      help="commit message")
    parser.add_option('--strict', dest='strict',
                      action='store_true', default=False,
                      help="bump dependencies specified as '==' but not '>='")
    parser.add_option('--git', dest='git_path', default='git',
                      help='git binary to use')
    parser.add_option('--pypi', dest='pypi_versions',
                      action='store_true', default=False,
                      help="display in-tree package versions and versions on pypi")
    options, args = parser.parse_args()
    globals()['dry_run'] = options.dry_run

    # get package information
    info = {}
    dependencies = {}
    directories = {}
    for package in setup_development.all_packages:
        directory = os.path.join(here, package)
        info[directory] = setup_development.info(directory)
        name, _dependencies = setup_development.get_dependencies(directory)
        assert name == info[directory]['Name']
        directories[name] = directory
        dependencies[name] = _dependencies

    if options.info:
        # print package version information and exit
        for value in info.values():
            print '%s %s : %s' % (value['Name'], value['Version'],
                                  ', '.join(dependencies[value['Name']]))
        parser.exit()

    if options.pypi_versions:
        # print package version information and version info from pypi and exit
        client = xmlrpclib.ServerProxy('http://pypi.python.org/pypi')
        for value in info.values():
            versions = client.package_releases(value['Name'])
            if versions:
                version = max(versions, key=lambda x: pkg_resources.parse_version(x))
            else:
                version = None
            print '%s %s : pypi version %s' % (value['Name'], value['Version'], version)
        parser.exit()

    # check for pypirc file
    if not options.diff: # you don't need this to write the diff
        home = os.environ['HOME']
        pypirc = os.path.join(home, '.pypirc')
        print "Checking for pypirc: %s" % pypirc
        if not os.path.exists(pypirc):
            parser.error("%s not found." % pypirc)

    # ensure git sanity
    # - ensure you are on the master branch
    cmd = [options.git_path, 'branch']
    process = subprocess.Popen(cmd,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               cwd=here)
    stdout, stderr = process.communicate()
    if stderr or process.returncode:
        print 'stdout:'
        print stdout
        print 'stderr:'
        print stderr
        raise CalledProcessError("Error running %s: %d" % (cmd,
                                                           process.returncode))
    branch = [line for line in stdout.splitlines() if line.startswith('*')][0]
    branch = branch.split('*', 1)[-1].strip()
    if branch != 'master':
        parser.error("versionbump.py must be used on the master branch")
    # - ensure there are no changes
    cmd = [options.git_path, 'status', '-s']
    process = subprocess.Popen(cmd,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               cwd=here)
    stdout, stderr = process.communicate()
    if stderr or process.returncode:
        raise CalledProcessError("Error running %s: %d" % (cmd,
                                                           process.returncode))
    if stdout.strip():
        parser.error("%s directory unclean when running git status -s" % here)

    # find desired versions
    if not args:
        parser.error("Please supply versions to bump")
    versions = {}
    msg = "Versions should be of the form 'package=version' (You gave: '%s')"
    for arg in args:
        if arg.count('=') != 1:
            parser.error(msg % arg)
        package, version = arg.split('=')
        versions[package] = version
    unrecognized = [package for package in versions
                    if package not in dependencies]
    if unrecognized:
        parser.error("Not a package: %s" % ', '.join(unrecognized))

    # record ancillary packages that need bumping
    # and ensure that if you're bumping versions, you're
    # bumping them for all packages affected
    dependent_versions = {}
    missing = []
    types = ['==']
    if not options.strict:
        types.append('>=')
    for name, deps in dependencies.items():
        for dep in deps:
            dep_info = setup_development.dependency_info(dep)
            if dep_info['Type'] in types and dep_info['Name'] in versions:
                if name not in versions:
                    missing.append(name)
                dependent_versions.setdefault(name, []).append(dep_info)

    if missing:
        missing = dict([('%s %s' % (i, info[directories[i]]['Version']),
                         [format_version(**k) for k in j])
                        for i, j in dependent_versions.items()
                        if i in missing])
        parser.error("Bumping %s, but you also need to bump %s" % (versions,
                                                                   missing))

    # ensure you are up to date
    print "Pulling from %s master" % REPOSITORY_PULL_URL
    call([options.git_path, 'pull', REPOSITORY_PULL_URL, 'master'],
         stdout=None, stderr=None, cwd=here)

    # bump versions of desired files
    for name, newversion in versions.items():
        directory = directories[name]
        oldversion = info[directory]['Version']
        print "Bumping %s == %s => %s" % (name, oldversion, newversion)
        setup_py = os.path.join(directory, 'setup.py')
        f = file(setup_py)
        lines = f.readlines()
        f.close()
        regex_string = r"""PACKAGE_VERSION *= *['"]%s["'].*""" % re.escape(oldversion)
        regex = re.compile(regex_string)
        for index, line in enumerate(lines):
            if regex.match(line):
                break
        else:
            revert(options.git_path)
            parser.error('PACKAGE_VERSION = "%s" not found in %s' % (version,
                                                                     setup_py))
        if not options.dry_run:
            lines[index] = "PACKAGE_VERSION = '%s'\n" % newversion
            f = file(setup_py, 'w')
            for line in lines:
                f.write(line)
            f.close()

    # bump version of dependencies
    for package, deps in dependent_versions.items():
        print "Bumping dependencies %s of %s" % ([format_version(**dep)
                                                  for dep in deps],
                                                 package)
        regexes = [(dep,
                    re.compile(r"%s *%s *%s" % (re.escape(dep['Name']),
                                                re.escape(dep['Type']),
                                                re.escape(dep['Version'])),
                               flags=re.MULTILINE)
                    )
                   for dep in deps]
        setup_py = os.path.join(directories[package], 'setup.py')
        assert os.path.exists(setup_py)
        f = file(setup_py)
        contents = f.read()
        f.close()
        matched = set()
        for dep, regex in regexes:
            newversion = '%s %s %s' % (dep['Name'], dep['Type'],
                                       versions[dep['Name']])
            formatted = format_version(**dep)
            print "- Bumping dependency %s => %s" % (formatted, newversion)
            matches = regex.findall(contents)
            if len(matches) != 1:
                revert(options.git_path)
                if not matches:
                    msg = "Could not find dependency %s in %s" % (formatted,
                                                                  setup_py)
                else:
                    msg = "Multiple matches for %s in %s" % (formatted,
                                                             setup_py)
                parser.error(msg)
            if not options.dry_run:
                contents = regex.sub(newversion, contents)
        if not options.dry_run:
            f = file(setup_py, 'w')
            f.write(contents)
            f.close()

    if options.diff and not options.dry_run:
        # write the diff
        if options.diff == '-':
            f = sys.stdout
            filename = 'stdout'
        else:
            f = file(options.diff, 'w')
            filename = options.diff
        print "Writing diff to %s" % filename
        process = subprocess.Popen([options.git_path, 'diff'],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   cwd=here)
        stdout, stderr = process.communicate()
        if process.returncode:
            print 'stdout:'
            print stdout
            print 'stderr:'
            print stderr
            parser.error("Error running `%s diff`" % options.git_path)
        f.write(stdout)
        if options.diff != '-':
            f.close()
        revert(options.git_path) # get back to your old state
        sys.exit()

    # push the changes
    if not options.message:
        print "No commit --message given; not updating git or pushing to pypi"
        sys.exit()
    print "Commit changes to %s: %s" % (REPOSITORY_URL, options.message)
    call([options.git_path, 'commit', '-a', '-m', options.message], cwd=here)
    call([options.git_path, 'push', REPOSITORY_URL, 'master'],
         stdout=None, stderr=None, cwd=here)

    # git tag the said versions
    tags = [('%s-%s' % (package, version))
            for package, version in versions.items()]
    print "Updating tags for %s: %s" % (REPOSITORY_URL, ', '.join(tags))
    call([options.git_path, 'pull', '--tags', REPOSITORY_URL, 'master'],
         stdout=None, stderr=None, cwd=here)
    for tag in tags:
        call([options.git_path, 'tag', tag], cwd=here)
    try:
        call([options.git_path, 'push', '--tags', REPOSITORY_URL, 'master'],
             stdout=None, stderr=None, cwd=here)
    except CalledProcessError, e:
        print "Failure pushing tags."
        raise e

    # upload to pypi
    formatted_deps = dict([(package, set([dep['Name'] for dep in deps]))
                           for package, dep in dependent_versions.items()])
    for package in versions.keys():
        formatted_deps.setdefault(package, set())
    unrolled = setup_development.unroll_dependencies(formatted_deps)
    print "Uploading to pypi: %s" % ', '.join([('%s-%s' % (package,
                                                           versions[package]))
                                               for package in unrolled])
    for package in unrolled:
        directory = directories[package]
        cmd = [sys.executable,
               'setup.py',
               'egg_info',
               '-RDb',
               '',
               'sdist',
               'upload']
        try:
            call(cmd, cwd=directory)
        except CalledProcessError, e:
            print """Failure uploading package %s to pypi.
Make sure you have permission to update the package
and that your ~/.pypirc file is correct""" % package
            raise e


if __name__ == '__main__':
    main()
