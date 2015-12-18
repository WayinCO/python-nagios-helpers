# -*- coding: utf-8 -*-
#
# Création : July 8th, 2015
#
# @author: Eric Lapouyade
#

import sys
import naghelp
from types import NoneType
import re

__all__ = [ 'ResponseLevel', 'PluginResponse', 'OK', 'WARNING', 'CRITICAL', 'UNKNOWN' ]

class ResponseLevel(object):
    """ Object to use when exiting a naghelp plugin

    Instead of using numeric code that may be hard to memorize, predefined objects has be created :

    =====================   =========
    Response level object   exit code
    =====================   =========
    OK                      0
    WARNING                 1
    CRITICAL                2
    UNKNOWN                 3
    =====================   =========

    To exit a plugin with the correct exit code number, one have just to call the :meth:`exit` method
    of the wanted ResonseLevel object
    """
    def __init__(self, name, exit_code):
        self.name = name
        self.exit_code = exit_code

    def __repr__(self):
        return self.name

    def info(self):
        """ Get name and exit code for a Response Level

        Examples:

            >>> level = CRITICAL
            >>> level.info()
            'CRITICAL (exit_code=2)'
            >>> level.name
            'CRITICAL'
            >>> level.exit_code
            2
        """
        return '%s (exit_code=%s)' % (self.name,self.exit_code)

    def exit(self):
        """ This is the official way to exit a naghelp plugin

        Example:

            >>> level = CRITICAL
            >>> level.exit()  #doctest: +SKIP
                SystemExit: 2
        """
        sys.exit(self.exit_code)

OK       = ResponseLevel('OK',0)
WARNING  = ResponseLevel('WARNING',1)
CRITICAL = ResponseLevel('CRITICAL',2)
UNKNOWN  = ResponseLevel('UNKNOWN',3)

class PluginResponse(object):
    """ Response to return to Nagios for a naghelp plugin

    Args:

        default_level (:class:`ResponseLevel`): The level to return when no level messages
            has been added to the response (for exemple when no error has be found).
            usually it is set to ``OK`` or ``UNKNOWN``

    A naghelp response has got many sections :

        * A synopsis (The first line that is directl visible onto Nagios interface)
        * A body (informations after the first line, only visible in detailed views)
        * Some performance Data

    The body itself has got some sub-sections :

        * Begin messages (Usually for a title, an introduction ...)
        * Levels messages, that are automatically splited into Nagios levels in this order:

            * Critical messages
            * Warning messages
            * Unkown messages
            * OK messages

        * More messages (Usually to give more information about the monitored host)
        * End messages (Custom conclusion messages. naghelp :class:`Plugin` use this section
            to add automatically some informations about the plugin.

    Each section can be updated by adding a message through dedicated methods.

    PluginResponse object takes care to calculate the right ResponseLevel to return to Nagios :
    it will depend on the Levels messages you will add to the plugin response. For example,
    if you add one ``OK`` message and one ``WARNING`` message, the response level will be
    ``WARNING``. if you add again one ``CRITICAL`` message then an ``OK`` message , the response
    level will be ``CRITICAL``.

    About the synopsis section : if not manualy set, the PluginResponse class will build one for
    you : It will be the unique level message if you add only one in the response or a summary
    giving the number of messages in each level.

    Examples:

        >>> r = PluginResponse(OK)
        >>> print r
        OK
        <BLANKLINE>

    """
    def __init__(self,default_level):
        self.level = None
        self.default_level = default_level
        self.sublevel = 0
        self.synopsis = None
        self.level_msgs = { OK:[], WARNING:[], CRITICAL:[], UNKNOWN:[] }
        self.begin_msgs = []
        self.more_msgs = []
        self.end_msgs = []
        self.perf_items = []

    def set_level(self, level):
        """ Manually set the response level

        Args:

            level (:class:`ResponseLevel`): OK, WARNING, CRITICAL or UNKNOWN

        Examples:

            >>> r = PluginResponse(OK)
            >>> print r.level
            None
            >>> r.set_level(WARNING)
            >>> print r.level
            WARNING
        """
        if not isinstance(level,ResponseLevel):
            raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))
        if self.level in [ None, UNKNOWN ] or level == CRITICAL or self.level == OK and level == WARNING:
            self.level = level

    def get_current_level(self):
        """ get current level

        If no level has not been set yet, it will return the default_level.
        Use this method if you want to know what ResponseLevel will be sent.

        Returns:

            :class:`ResponseLevel` : the response level to be sent

        Examples:

            >>> r = PluginResponse(OK)
            >>> print r.get_current_level()
            OK
            >>> r.set_level(WARNING)
            >>> print r.get_current_level()
            WARNING
        """
        return self.default_level if self.level is None else self.level

    def set_sublevel(self, sublevel):
        """ sets sublevel attribute

        Args:

            sublevel (int): 0,1,2 or 3  (Default : 0)

        From time to time, the CRITICAL status meaning is not detailed enough :
        It may be useful to color it by a sub-level.
        The ``sublevel`` value is not used directly by :class:`PluginResponse`,
        but by :class:`ActivePlugin` class which adds a ``__sublevel__=<sublevel>`` string
        in the plugin informations section. This string can be used for external filtering.

        Actually, the sublevel meanings are :

        =========  ===========================================================================
        Sub-level  Description
        =========  ===========================================================================
        0          The plugin is 100% sure there is a critical error
        1          The plugin was able to contact remote host but got no answer from agent
        2          The plugin was unable to contact the remote host, it may be a network issue
        3          The plugin raised an unexpected exception : it should be a bug.
        =========  ===========================================================================
        """
        if not isinstance(sublevel,int):
            raise Exception('A response sublevel must be an integer')
        self.sublevel = sublevel

    def get_sublevel(self):
        """ get sublevel

        Returns:

            int: sublevel (0,1,2 or 3)

        Exemples:

            >>> r = PluginResponse(OK)
            >>> print r.get_sublevel()
            0
            >>> r.set_sublevel(2)
            >>> print r.get_sublevel()
            2
        """
        return self.sublevel


    def _reformat_msg(self,msg,*args,**kwargs):
        if isinstance(msg,(list,tuple)):
            msg = '\n'.join(msg)
        elif not isinstance(msg,basestring):
            msg = str(msg)
        if args:
            msg = msg % args
        if kwargs:
            msg = msg.format(**kwargs)
        return msg

    def add_begin(self,msg,*args,**kwargs):
        r""" Add a message in begin section

        You can use this method several times and at any time until the :meth:`send` is used.
        The messages will be displayed in begin section in the same order as they have been added.
        This method does not change the calculated ResponseLevel.

        Args:

            msg (str): the message to add in begin section.
            args (list): if additionnal arguments are given,
                ``msg`` will be formatted with ``%`` (old-style python string formatting)
            kwargs (dict): if named arguments are give,
                ``msg`` will be formatted with :meth:`str.format`

        Examples:

            >>> r = PluginResponse(OK)
            >>> r.add_begin('='*40)
            >>> r.add_begin('{hostname:^40}', hostname='MyHost')
            >>> r.add_begin('='*40)
            >>> r.add_begin('Date : %s, Time : %s','2105-12-18','14:55:11')
            >>> r.add_begin('\n')
            >>> r.add(CRITICAL,'This is critical !')
            >>> print r     #doctest: +NORMALIZE_WHITESPACE
            This is critical !
            ========================================
                             MyHost
            ========================================
            Date : 2105-12-18, Time : 14:55:11
            <BLANKLINE>
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            This is critical !
            <BLANKLINE>
            <BLANKLINE>
        """
        self.begin_msgs.append(self._reformat_msg(msg,*args,**kwargs))

    def add(self,level,msg,*args,**kwargs):
        if isinstance(level,ResponseLevel):
            self.level_msgs[level].append(self._reformat_msg(msg,*args,**kwargs))
            self.set_level(level)
        else:
            raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))

    def add_list(self,level,msg_list,*args,**kwargs):
        for msg in msg_list:
            if msg:
                self.add(level, msg,*args,**kwargs)

    def add_many(self,lst,*args,**kwargs):
        for level,msg in lst:
            self.add(level, msg,*args,**kwargs)

    def add_if(self, test, level, msg=None, *args,**kwargs):
        if msg is None:
            msg = test
        if isinstance(level,ResponseLevel):
            if test:
                self.add(level,msg,*args,**kwargs)
                self.set_level(level)
        else:
            raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))

    def add_elif(self,*add_ifs,**kwargs):
        for test,level,msg in add_ifs:
            if msg is None:
                msg = test
            if isinstance(level,ResponseLevel):
                if test:
                    self.add(level,msg,**kwargs)
                    self.set_level(level)
                    break
            else:
                raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))

    def add_more(self,msg,*args,**kwargs):
        if isinstance(msg,(list,tuple)):
            msg = '\n'.join(msg)
        elif not isinstance(msg,basestring):
            msg = str(msg)
        if args:
            msg = msg % args
        if kwargs:
            msg = msg.format(**kwargs)
        self.more_msgs.append(msg)

    def add_end(self,msg,*args,**kwargs):
        r""" Add a message in end section

        You can use this method several times and at any time until the :meth:`send` is used.
        The messages will be displayed in end section in the same order as they have been added.
        This method does not change the calculated ResponseLevel.

        Args:

            msg (str): the message to add in end section.
            args (list): if additional arguments are given,
                ``msg`` will be formatted with ``%`` (old-style python string formatting)
            kwargs (dict): if named arguments are give,
                ``msg`` will be formatted with :meth:`str.format`

        Examples:

            >>> r = PluginResponse(OK)
            >>> r.add_end('='*40)
            >>> r.add_end('{hostname:^40}', hostname='MyHost')
            >>> r.add_end('='*40)
            >>> r.add_end('Date : %s, Time : %s','2105-12-18','14:55:11')
            >>> r.add_end('\n')
            >>> r.add(CRITICAL,'This is critical !')
            >>> print r     #doctest: +NORMALIZE_WHITESPACE
            This is critical !
            <BLANKLINE>
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            This is critical !
            <BLANKLINE>
            <BLANKLINE>
            ========================================
                             MyHost
            ========================================
            Date : 2105-12-18, Time : 14:55:11
        """
        if isinstance(msg,(list,tuple)):
            msg = '\n'.join(msg)
        elif not isinstance(msg,basestring):
            msg = str(msg)
        if args:
            msg = msg % args
        if kwargs:
            msg = msg.format(**kwargs)
        self.end_msgs.append(msg)


    def add_perf_data(self,data):
        """ Add performance object into the response """
        if not isinstance(data,basestring):
            data = str(data)
        self.perf_items.append(data)

    def set_synopsis(self,msg,*args,**kwargs):
        if not isinstance(msg,basestring):
            msg = str(msg)
        if args:
            msg = msg % args
        if kwargs:
            msg = msg.format(**kwargs)
        self.synopsis = msg

    def get_default_synopsis(self):
        nb_ok = len(self.level_msgs[OK])
        nb_nok = len(self.level_msgs[WARNING]) + len(self.level_msgs[CRITICAL]) + len(self.level_msgs[UNKNOWN])
        if nb_ok + nb_nok == 0:
            return str(self.level or self.default_level or UNKNOWN)
        if nb_ok and not nb_nok:
            return str(OK)
        if nb_nok == 1:
            return re.sub(r'^(.{75}).*$', '\g<1>...',(self.level_msgs[WARNING] + self.level_msgs[CRITICAL] + self.level_msgs[UNKNOWN])[0])
        return 'STATUS : ' + ', '.join([ '%s:%s' % (level,len(self.level_msgs[level])) for level in [CRITICAL, WARNING, UNKNOWN, OK ] if self.level_msgs[level] ])

    def section_format(self,title):
        return '{0:=^80}'.format('[ {0:^8} ]'.format(title))

    def subsection_format(self,title):
        return '----' + '{0:-<76}'.format('( %s )' % title)

    def level_msgs_render(self):
        out = self.section_format('STATUS') + '\n'
        have_status = False
        for level in [CRITICAL, WARNING, UNKNOWN, OK ]:
            msgs = self.level_msgs[level]
            if msgs:
                have_status = True
                out += '\n'
                out += self.subsection_format(level) + '\n'
                out += '\n'.join(msgs)
                out += '\n'

        if not have_status:
            return ''
        out += '\n'
        return out

    def escape_msg(self,msg):
        return msg.replace('|','!')

    def get_output(self):
        synopsis = self.synopsis or self.get_default_synopsis()
        synopsis = synopsis.splitlines()[0]
        synopsis = synopsis[:75] + ( synopsis[75:] and '...' )

        out = self.escape_msg(synopsis)
        out +=  '|%s' % self.perf_items[0] if self.perf_items else '\n'

        body = '\n'.join(self.begin_msgs)
        body += self.level_msgs_render()
        if self.more_msgs:
            body += self.section_format('Additionnal informations') + '\n'
            body += '\n'.join(self.more_msgs)
        body += '\n'.join(self.end_msgs)

        out += self.escape_msg(body)
        out +=  '|%s' % '\n'.join(self.perf_items[1:]) if len(self.perf_items)>1 else ''
        return out

    def __str__(self):
        return self.get_output()

    def send(self, level=None, synopsis='', msg='', sublevel = None):
        if isinstance(level,ResponseLevel):
            self.set_level(level)
        if self.level is None:
            self.level = self.default_level or UNKNOWN
        if synopsis:
            self.synopsis = synopsis
        if msg:
            self.add(level,msg)
        if sublevel is not None:
            self.set_sublevel(sublevel)

        naghelp.logger.info('Plugin output summary : %s' % self.synopsis)

        out = self.get_output()

        naghelp.logger.debug('Plugin output :\n' + '#' * 80 + '\n' + out + '\n'+ '#' * 80)

        print out

        naghelp.logger.info('Exiting plugin with response level : %s, __sublevel__=%s', self.level.info(), self.sublevel )
        self.level.exit()
