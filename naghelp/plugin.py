# -*- coding: utf-8 -*-
'''
Création : July 8th, 2015

@author: Eric Lapouyade
'''

import os
import sys
import re
import json
from optparse import OptionParser, OptionGroup
import traceback
import logging
import logging.handlers
import pprint
from .host import Host
from .response import PluginResponse, OK, WARNING, CRITICAL, UNKNOWN
import tempfile
from textops import DictExt, NoAttr
from collect import search_invalid_port
import datetime
#
pp = pprint.PrettyPrinter(indent=4)

__all__ = [ 'ActivePlugin' ]

class Plugin(object):
    plugin_type = 'abstract'
    logger_name = 'naghelp'
    logger_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logger_logsize = 1000000
    logger_logbackup = 5

    def get_cmd_usage(self):
        return self.usage

    def get_plugin_desc(self):
        return ''

    def init_cmd_options(self):
        self._cmd_parser = OptionParser(usage = self.get_cmd_usage())
        self._cmd_parser.add_option('-v', action='store_true', dest='verbose',
                                   default=False, help='Verbose : display informational messages')
        self._cmd_parser.add_option('-d', action='store_true', dest='debug',
                                   default=False, help='Debug : display debug messages')
        self._cmd_parser.add_option('-l', action='store', dest='logfile', metavar="FILE",
                                   help='Redirect logs into a file')
        self._cmd_parser.add_option('-i', action='store_true', dest='show_description',
                                   default=False, help='Display plugin description')

    def add_cmd_options(self):
        pass

    def get_logger_name(self):
        return self.logger_name

    def get_logger_format(self):
        return self.logger_format

    def get_logger_level(self):
        if self.options.debug:
            return logging.DEBUG
        elif self.options.verbose:
            return logging.INFO
        return logging.CRITICAL

    def get_logger_file_level(self):
        return self.get_logger_level()

    def get_logger_console_level(self):
        return self.get_logger_level()

    def get_logger_file_logfile(self):
        return self.options.logfile

    def add_logger_file_handler(self):
        logfile = self.get_logger_file_logfile()
        if logfile:
            fh = logging.handlers.RotatingFileHandler(logfile, maxBytes=self.logger_logsize,
                                                           backupCount=self.logger_logbackup)
            fh.setLevel(self.get_logger_file_level())
            formatter = logging.Formatter(self.logger_format)
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
            self.debug('Debug log file = %s' % logfile)

    def add_logger_console_handler(self):
        ch = logging.StreamHandler()
        ch.setLevel(self.get_logger_console_level())
        formatter = logging.Formatter(self.logger_format)
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def init_logger(self):
        self.logger = logging.getLogger(self.get_logger_name())
        self.logger.setLevel(logging.DEBUG)
        self.add_logger_console_handler()
        self.add_logger_file_handler()

    def handle_cmd_options(self):
        (options, args) = self._cmd_parser.parse_args()
        self.options = options
        self.args = args
        if self.options.show_description:
            print self.__class__.__doc__
            exit(0)

    def manage_cmd_options(self):
        self.init_cmd_options()
        self.add_cmd_options()
        self.handle_cmd_options()

    def error(self,msg,*args,**kwargs):
        self.logger.error(msg,*args,**kwargs)

    def warning(self,msg,*args,**kwargs):
        self.logger.warning(msg,*args,**kwargs)

    def info(self,msg,*args,**kwargs):
        self.logger.info(msg,*args,**kwargs)

    def debug(self,msg,*args,**kwargs):
        self.logger.debug(msg,*args,**kwargs)

    def save_data(self,filename,data, ignore_error = True):
        self.debug('Saving data to %s :\n%s',filename,pp.pformat(data))
        try:
            filedir = os.path.dirname(filename)
            if not os.path.exists(filedir):
                os.makedirs(filedir)
            with open(filename,'w') as fh:
                json.dump(data,fh,indent=4,default=datetime_handler)
        except Exception,e:
            self.debug('Exception : %s',e)
            if not ignore_error:
                raise

    def load_data(self,filename):
        self.debug('Loading data from %s :',filename)
        try:
            with open(filename) as fh:
                data = DictExt(json.load(fh))
                self.debug(pp.pformat(data))
                return data
        except (IOError, OSError, ValueError),e:
            self.debug('Exception : %s',e)
        self.debug('No data found')
        return NoAttr

class ActivePlugin(Plugin):
    plugin_type = 'active'
    host_class = Host
    response_class = PluginResponse
    usage = 'usage: \n%prog <module.plugin_class> [options]'
    cmd_params = ''
    required_params = ''
    tcp_ports = ''
    udp_ports = ''
    nagios_status_on_error = CRITICAL
    collected_data_filename_pattern = '/tmp/naghelp/%s_collected_data.json'
    data = DictExt()

    def __init__(self):
        self.response = self.response_class(self)

    def get_plugin_host_params_tab(self):
        return {    'name'  : 'Hostname',
                    'ip'    : 'Host IP address',
                }

    def get_plugin_host_params_desc(self):
        params_tab = self.get_plugin_host_params_tab()
        cmd_params = self.cmd_params.split(',') if isinstance(self.cmd_params,basestring) else self.cmd_params
        cmd_params = set(cmd_params).union(['name','ip'])
        return dict([(k,params_tab.get(k,k.title())) for k in cmd_params ])

    def get_plugin_required_params(self):
        required_params = self.required_params.split(',') if isinstance(self.required_params,basestring) else self.required_params
        return set(required_params).union(['ip'])


    def init_cmd_options(self):
        super(ActivePlugin,self).init_cmd_options()

        group = OptionGroup(self._cmd_parser, 'Host attributes','To be used to force host attributes values')
        for param,desc in self.get_plugin_host_params_desc().items():
            group.add_option('--%s' % param, action='store', type='string', dest="host__%s" % param, metavar=param.upper(), help=desc)
        self._cmd_parser.add_option_group(group)

        self._cmd_parser.add_option('-s', action='store_true', dest='save_collected',
                                   default=False, help='Save collected data in a temporary file')
        self._cmd_parser.add_option('-r', action='store_true', dest='restore_collected',
                                   default=False, help='Use saved collected data (option -s)')

    def handle_cmd_options(self):
        super(ActivePlugin,self).handle_cmd_options()
        if self.options.show_description:
            print self.get_plugin_desc()
            UNKNOWN.exit()

    def error(self,msg,*args,**kwargs):
        import traceback
        msg += '\n\n' + traceback.format_exc() + '\n'
        if self.data:
            msg += 'Data = \n%s\n\n' % pp.pformat(self.data)
        self.logger.error(msg,*args,**kwargs)
        print msg % args
        self.nagios_status_on_error.exit()

    def warning(self,msg,*args,**kwargs):
        self.logger.warning(msg,*args,**kwargs)
        self.response.add(msg % args,WARNING)

    def get_collected_data_filename(self):
        hostname = self.host.name or 'unknown_host'

    def save_collected_data(self):
        self.save_data(self.collected_data_filename_pattern % self.host.name, self.data)

    def restore_collected_data(self):
        self.data = self.load_data(self.collected_data_filename_pattern % self.host.name)

    def check_ports(self):
        invalid_port = search_invalid_port(self.host.ip,self.tcp_ports)
        if invalid_port:
            self.response.send(CRITICAL,'Port %s is unreachable, please check your firewall for tcp ports : %s' % (invalid_port,self.tcp_ports))

    def collect_data(self,data):
        pass

    def parse_data(self,data):
        pass

    def build_response(self,data):
        pass

    def run(self):
        try:
            self.manage_cmd_options()
            self.host = self.host_class(self)
            self.init_logger()
            self.info('Start plugin %s.%s for %s' % (self.__module__,self.__class__.__name__,self.host.name))
            self.host.load_persistent_data()
            self.host.debug()

            if self.options.restore_collected:
                self.restore_collected_data()
                self.info('Collected data are restored')
            else:
                try:
                    self.collect_data(self.data)
                except Exception,e:
                    if self.tcp_ports:
                        self.info('Checking TCP ports %s ...' % self.tcp_ports)
                        self.check_ports()
                        self.info('All TCP ports are reachable')
                    else:
                        self.info('No port to check')
                    msg = 'Failed to collect equipment status : %s\n' % e
                    if self.tcp_ports:
                        msg += 'Please check your firewall for TCP ports : %s' % self.tcp_ports
                    if self.tcp_ports:
                        msg += 'Please check your firewall for UDP ports : %s' % self.udp_ports
                    self.error(msg)

                self.info('Data are collected')
            self.debug('Collected Data = \n%s' % pp.pformat(self.data))
            collected_keys = self.data.keys()

            if self.options.save_collected:
                self.save_collected_data()
                self.info('Collected data are saved')

            self.parse_data(self.data)
            self.info('Data are parsed')
            self.debug('Parsed Data = \n%s' % pp.pformat(self.data.exclude(collected_keys)))

            self.build_response(self.data)
            self.host.save_persistent_data()
            self.response.send()
        except Exception,e:
            if not hasattr(self,'logger'):
                import traceback
                msg = 'Plugin internal error %s\n\n%s' % (e,traceback.format_exc())
                print msg
            self.error('Plugin internal error : %s' % e)

        self.error('Should never reach this point')

def datetime_handler(obj):
    if isinstance(obj, (datetime.datetime,datetime.date)):
        return obj.isoformat()
    return None

