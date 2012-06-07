[Mozinstall](https://github.com/mozilla/mozbase/tree/master/mozinstall) is a
python package for installing and uninstalling Mozilla applications on
various platforms.

For example, depending on the platform, Firefox can be distributed as a 
zip, tar.bz2, exe, or dmg file or cloned from a repository. Mozinstall takes
the hassle out of extracting and/or running these files and for convenience
returns the full path to the install directory. In the case that mozinstall
is invoked from the command line, the binary path will be printed to stdout.

To remove an installed applicatoin the uninstaller can be used. It requires
the installation path of the application and will remove all the installed
files. On Windows the uninstaller will be tried first.

# Usage

For command line options run mozinstall --help

Mozinstall's main function is the install method:

    import mozinstall
    path = mozinstall.install(%installer%, %install_folder%)

To retrieve the binary of the application call get_binary with the path and
the application name:

    mozinstall.get_binary(path, 'firefox')

If the application is not needed anymore the uninstaller will remove all
traces from the system:

    mozinstall.uninstall(path)

# Error Handling

Mozinstall throws different types of exceptions:

- mozinstall.InstallError is thrown when the installation fails for any reason. A traceback is provided.
- mozinstall.InvalidBinary is thrown when the binary cannot be found.
- mozinstall.InvalidSource is thrown when the source is not a recognized file type (zip, exe, tar.bz2, tar.gz, dmg).


# Dependencies

Mozinstall depends on the [mozinfo](https://github.com/mozilla/mozbase/tree/master/mozinfo) 
package which is also found in the mozbase repository.
