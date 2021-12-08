python-zeroconf-py2compat
=========================
    
This is a fork of pyzeroconf, Multicast DNS Service Discovery for Python,
originally by Paul Scott-Murphy (https://github.com/paulsm/pyzeroconf),
modified by William McBrine (https://github.com/wmcbrine/pyzeroconf),
and then further modified (off the 0.19.1 tag, the last to support Py2.7)
by Jamie Alexandre (https://github.com/learningequality/python-zeroconf).

Compatible with:

* Bonjour
* Avahi

Compared to some other Zeroconf/Bonjour/Avahi Python packages, python-zeroconf:

* isn't tied to Bonjour or Avahi
* doesn't use D-Bus
* doesn't force you to use particular event loop or Twisted
* is pip-installable

Python compatibility
--------------------

* CPython 2.7, 3.3+
* PyPy 2.2+ (possibly 1.9-2.1 as well)
* PyPy3 2.4+

Versioning
----------

This project's versions follow the following pattern: MAJOR.MINOR.PATCH.

* MAJOR version has been 0 so far
* MINOR version is incremented on backward incompatible changes
* PATCH version is incremented on backward compatible changes

Status
------

There are some people using this package. I don't actively use it and as such
any help I can offer with regard to any issues is very limited.


How to get python-zeroconf-py2compat?
=====================================

* PyPI page https://pypi.python.org/pypi/zeroconf-py2compat
* GitHub project https://github.com/learningequality/python-zeroconf-py2compat

The easiest way to install python-zeroconf-py2compat is using pip::

    pip install zeroconf-py2compat



How do I use it?
================

Here's an example of browsing for a service:

.. code-block:: python

    from six.moves import input
    from zeroconf import ServiceBrowser, Zeroconf
    
    
    class MyListener(object):
    
        def remove_service(self, zeroconf, type, name):
            print("Service %s removed" % (name,))
    
        def add_service(self, zeroconf, type, name):
            info = zeroconf.get_service_info(type, name)
            print("Service %s added, service info: %s" % (name, info))
    
    
    zeroconf = Zeroconf()
    listener = MyListener()
    browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)
    try:
        input("Press enter to exit...\n\n")
    finally:
        zeroconf.close()

.. note::

    Discovery and service registration use *all* available network interfaces by default.
    If you want to customize that you need to specify ``interfaces`` argument when
    constructing ``Zeroconf`` object (see the code for details).

If you don't know the name of the service you need to browse for, try:

.. code-block:: python

    from zeroconf import ZeroconfServiceTypes
    print('\n'.join(ZeroconfServiceTypes.find()))

See examples directory for more.

Changelog
=========

0.19.14
-------
- Exclude addresses starting with "169.254" from the list returned by get_all_addresses()

0.19.13
-------
* Converts some usage of `assert` that should likely persist if `python -O` is used
* Breaks out interface attachment from `Zeroconf.__init__` into its own method `_add_interfaces`
* Adds corresponding behavior for removing interfaces, along the lines of how `_add_interfaces` functions but in reverse
* Exposes new public method `Zeroconf.update_interfaces` which triggers add or removal of interfaces
* Prevents stack trace reporting of errors that occur because the network is unreachable, `errno.ENETUNREACH`
* Updates `Zeroconf.send` to accept an `interface` on which filter the interfaces it sends the messages on,
  such that adding and removing interfaces can attempt to send add/remove messages when the interface is removed

0.19.10
-------
Reduce (and make configurable) the _GLOBAL_DONE threading wait time to improve discovery.

0.19.9
------
Turn _GLOBAL_DONE into a threading Event to allow for better interruptability at close.

0.19.8
------
Handle exceptions in interface enumeration and just return an empty list.

0.19.7
------
Reverted from ifaddr back to ifcfg.

0.19.6
------
Switched from ifcfg to ifaddr for address enumeration.

0.19.5
------
Add support for Android, via pyjnius.

0.19.4
------
Vendored enum compat.

0.19.3
------
* Fix to setup.py, so as to actually include zeroconf.py!

0.19.2 (first release in learningequality/python-zeroconf-py2compat)
--------------------------------------------------------------------
* Replace C-based netifaces with pure-Python ifcfg for portability
* Allow the DNS A record address to be determined by outgoing interface IP
* Refresh ServiceBrowser entries already when 'stale' (backport from 0.20.0)
* Add new records first in cache entry instead of last (backport from 0.20.0)
* Correct broken __eq__ in child classes to DNSRecord (backport from 0.20.0)
* Fix TTL handling for published service, and use RFC6762 (backport from 0.21.0)
* Fix UnboundLocalError for count after loop (backport from 0.21.0)
* Fix UTF-8 multibyte name compression (backport from 0.21.0)
* Fix a logging call (backport from 0.21.0)
* Fix service removal packets not being sent on shutdown (backport from 0.22.0)
* MyListener callback on service TXT record changes (backport from 0.23.0)

0.19.1
------

* Allowed installation with netifaces >= 0.10.6 (a bug that was concerning us
  got fixed)

0.19.0
------

* Technically backwards incompatible - restricted netifaces dependency version to
  work around a bug, see https://github.com/jstasiak/python-zeroconf/issues/84 for
  details

0.18.0
------

* Dropped Python 2.6 support
* Improved error handling inside code executed when Zeroconf object is being closed

0.17.7
------

* Better Handling of DNS Incoming Packets parsing exceptions
* Many exceptions will now log a warning the first time they are seen
* Catch and log sendto() errors
* Fix/Implement duplicate name change
* Fix overly strict name validation introduced in 0.17.6
* Greatly improve handling of oversized packets including:

  - Implement name compression per RFC1035
  - Limit size of generated packets to 9000 bytes as per RFC6762
  - Better handle over sized incoming packets

* Increased test coverage to 95%

0.17.6
------

* Many improvements to address race conditions and exceptions during ZC()
  startup and shutdown, thanks to: morpav, veawor, justingiorgi, herczy,
  stephenrauch
* Added more test coverage: strahlex, stephenrauch
* Stephen Rauch contributed:

  - Speed up browser startup
  - Add ZeroconfServiceTypes() query class to discover all advertised service types
  - Add full validation for service names, types and subtypes
  - Fix for subtype browsing
  - Fix DNSHInfo support

0.17.5
------

* Fixed OpenBSD compatibility, thanks to Alessio Sergi
* Fixed race condition on ServiceBrowser startup, thanks to gbiddison
* Fixed installation on some Python 3 systems, thanks to Per Sandström
* Fixed "size change during iteration" bug on Python 3, thanks to gbiddison

0.17.4
------

* Fixed support for Linux kernel versions < 3.9 (thanks to Giovanni Harting
  and Luckydonald, GitHub pull request #26)

0.17.3
------

* Fixed DNSText repr on Python 3 (it'd crash when the text was longer than
  10 bytes), thanks to Paulus Schoutsen for the patch, GitHub pull request #24

0.17.2
------

* Fixed installation on Python 3.4.3+ (was failing because of enum34 dependency
  which fails to install on 3.4.3+, changed to depend on enum-compat instead;
  thanks to Michael Brennan for the original patch, GitHub pull request #22)

0.17.1
------

* Fixed EADDRNOTAVAIL when attempting to use dummy network interfaces on Windows,
  thanks to daid

0.17.0
------

* Added some Python dependencies so it's not zero-dependencies anymore
* Improved exception handling (it'll be quieter now)
* Messages are listened to and sent using all available network interfaces
  by default (configurable); thanks to Marcus Müller
* Started using logging more freely
* Fixed a bug with binary strings as property values being converted to False
  (https://github.com/jstasiak/python-zeroconf/pull/10); thanks to Dr. Seuss
* Added new ``ServiceBrowser`` event handler interface (see the examples)
* PyPy3 now officially supported
* Fixed ServiceInfo repr on Python 3, thanks to Yordan Miladinov

0.16.0
------

* Set up Python logging and started using it
* Cleaned up code style (includes migrating from camel case to snake case)

0.15.1
------

* Fixed handling closed socket (GitHub #4)

0.15
----

* Forked by Jakub Stasiak
* Made Python 3 compatible
* Added setup script, made installable by pip and uploaded to PyPI
* Set up Travis build
* Reformatted the code and moved files around
* Stopped catching BaseException in several places, that could hide errors
* Marked threads as daemonic, they won't keep application alive now

0.14
----

* Fix for SOL_IP undefined on some systems - thanks Mike Erdely.
* Cleaned up examples.
* Lowercased module name.

0.13
----

* Various minor changes; see git for details.
* No longer compatible with Python 2.2. Only tested with 2.5-2.7.
* Fork by William McBrine.

0.12
----

* allow selection of binding interface
* typo fix - Thanks A. M. Kuchlingi
* removed all use of word 'Rendezvous' - this is an API change

0.11
----

* correction to comments for addListener method
* support for new record types seen from OS X
  - IPv6 address
  - hostinfo

* ignore unknown DNS record types
* fixes to name decoding
* works alongside other processes using port 5353 (e.g. on Mac OS X)
* tested against Mac OS X 10.3.2's mDNSResponder
* corrections to removal of list entries for service browser

0.10
----

* Jonathon Paisley contributed these corrections:

  - always multicast replies, even when query is unicast
  - correct a pointer encoding problem
  - can now write records in any order
  - traceback shown on failure
  - better TXT record parsing
  - server is now separate from name
  - can cancel a service browser
  
* modified some unit tests to accommodate these changes

0.09
----

* remove all records on service unregistration
* fix DOS security problem with readName

0.08
----

* changed licensing to LGPL

0.07
----

* faster shutdown on engine
* pointer encoding of outgoing names
* ServiceBrowser now works
* new unit tests

0.06
----
* small improvements with unit tests
* added defined exception types
* new style objects
* fixed hostname/interface problem
* fixed socket timeout problem
* fixed add_service_listener() typo bug
* using select() for socket reads
* tested on Debian unstable with Python 2.2.2

0.05
----

* ensure case insensitivty on domain names
* support for unicast DNS queries

0.04
----

* added some unit tests
* added __ne__ adjuncts where required
* ensure names end in '.local.'
* timeout on receiving socket for clean shutdown


License
=======

LGPL, see COPYING file for details.
