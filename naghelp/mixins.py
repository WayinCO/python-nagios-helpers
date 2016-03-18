# -*- coding: utf-8 -*-
'''
Création : 19 Aout 2015

@author: Eric Lapouyade
'''

from textops import *

__all__ = ['GaugeMixin','GaugeException']

class GaugeException(Exception):
    pass

class GaugeMixin(object):
    def gauge_response_threshold_list(self,id,label_values,warn_min=None,crit_min=None,warn_max=None,crit_max=None):
        for i,(label,value) in enumerate(label_values):
            self.gauge_response_threshold('%s%s' % (id,i),label,value,warn_min=warn_min,crit_min=crit_min,warn_max=warn_max,crit_max=crit_max)

    def gauge_response_factor_list(self,id,label_values,warn_min=None,crit_min=None,warn_max=None,crit_max=None):
        for i,(label,value) in enumerate(label_values):
            self.gauge_response_factor('%s%s' % (id,i),label,value,warn_min=warn_min,crit_min=crit_min,warn_max=warn_max,crit_max=crit_max)

    def gauge_response_threshold(self,id,label,value,warn_min=None,crit_min=None,warn_max=None,crit_max=None):
        self.response.add_more('%s : %s',label,value)
        self.debug('Gauge id=%s, value=%s (warn_min=%s,crit_min=%s,warn_max=%s,crit_max=%s)',id,value,warn_min,crit_min,warn_max,crit_max)        
        if isinstance(value,basestring):
            value = find_pattern.op(value,r'([\d,\.]+)').replace(',','.')
            if value:
                value=float(value)
        if isinstance(value,(int,float)): 
            if isinstance(crit_min,(int,float)) and value <= crit_min:
                self.response.add(CRITICAL,'%s : %s <= MIN CRITICAL (%s)' % (label, value, crit_min))
            elif isinstance(warn_min,(int,float)) and value <= warn_min:
                self.response.add(WARNING,'%s : %s <= MIN WARNING (%s)' % (label, value, warn_min))
            elif isinstance(crit_max,(int,float)) and value >= crit_max:
                self.response.add(CRITICAL,'%s : %s >= MAX CRITICAL (%s)' % (label, value, crit_max))
            elif isinstance(warn_max,(int,float)) and value >= warn_max:
                self.response.add(WARNING,'%s : %s >= MAX WARNING (%s)' % (label, value, warn_max))
            
    def gauge_response_factor(self,id,label,value,warn_min=None,crit_min=None,warn_max=None,crit_max=None):
        self.response.add_more('%s : %s',label,value)
        self.debug('Gauge id=%s, value=%s (warn_min=%s,crit_min=%s,warn_max=%s,crit_max=%s)',id,value,warn_min,crit_min,warn_max,crit_max)        
        if isinstance(value,basestring):
            value = find_pattern.op(value,r'([\d,\.]+)').replace(',','.')
            if value:
                value=float(value)
        if isinstance(value,(int,float)):            
            if isinstance(crit_min,(int,float)) and value <= value*crit_min:
                self.response.add(CRITICAL,'%s : %s <= MIN CRITICAL (%s)' % (label, value, value*crit_min))
            elif isinstance(warn_min,(int,float)) and value <= value*warn_min:
                self.response.add(WARNING,'%s : %s <= MIN WARNING (%s)' % (label, value, value*warn_min))
            elif isinstance(crit_max,(int,float)) and value >= value*crit_max:
                self.response.add(CRITICAL,'%s : %s >= MAX CRITICAL (%s)' % (label, value, value*crit_max))
            elif isinstance(warn_max,(int,float)) and value >= value*warn_max:
                self.response.add(WARNING,'%s : %s >= MAX WARNING (%s)' % (label, value, value*warn_max))
            
    def gauge_response_etalon_change(self,id,label,value,level):
        self.response.add_more('%s : %s',label,value)
        etalon_name = id + '_etalon'
        etalon_value = self.host.get(etalon_name,None)
        self.debug('Gauge id=%s, was:%s, now:%s',id,etalon_value,value)
        if etalon_value is not None and value < etalon_value:
            self.response.add(level,'%s : actual value (%s) has changed (was %s)' % (label, value, etalon_value))
        if isinstance(value,(int,float)):
            # save the gauge value as the new reference value in host's persistent data
            self.host.set(etalon_name,value)
            
    def gauge_response_etalon_down(self,id,label,value,level):
        self.response.add_more('%s : %s',label,value)
        etalon_name = id + '_etalon'
        etalon_value = self.host.get(etalon_name,None)
        self.debug('Gauge id=%s, was:%s, now:%s',id,etalon_value,value)
        if etalon_value is not None and value < etalon_value:
            self.response.add(level,'%s : actual value (%s) is less than the reference value (%s)' % (label, value, etalon_value))
        if isinstance(value,(int,float)):
            # save the gauge value as the new reference value in host's persistent data
            self.host.set(etalon_name,value)
            
    def gauge_response_etalon_up(self,id,label,value,level):
        self.response.add_more('%s : %s',label,value)
        etalon_name = id + '_etalon'
        etalon_value = self.host.get(etalon_name,None)
        self.debug('Gauge id=%s, was:%s, now:%s',id,etalon_value,value)
        if etalon_value is not None and value > etalon_value:
            self.response.add(level,'%s : actual value (%s) is more than the reference value (%s)' % (label, value, etalon_value))
        if isinstance(value,(int,float)):
            # save the gauge value as the new reference value in host's persistent data
            self.host.set(etalon_name,value)