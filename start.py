#!/usr/bin/python3
# -*- coding:utf-8 -*-

import http.client
import requests
import datetime
from xml.etree.ElementTree import *
from http.server import HTTPServer, SimpleHTTPRequestHandler
import dateutil.parser
from configparser import SafeConfigParser

class garoon:
    def __get_xml(self, day):
        config = SafeConfigParser()
        config.read('grn2ical.conf')
    
        body = """<?xml version="1.0" encoding="UTF-8"?>
        <SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope"
         xmlns:xsd="http://www.w3.org/2001/XMLSchema"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"
         xmlns:base_services="http://wsdl.cybozu.co.jp/base/2008">
          <SOAP-ENV:Header>
            <Action SOAP-ENV:mustUnderstand="1"
             xmlns="http://schemas.xmlsoap.org/ws/2003/03/addressing">
              ScheduleGetEvents
            </Action>
            <Security xmlns:wsu="http://schemas.xmlsoap.org/ws/2002/07/utility"
             SOAP-ENV:mustUnderstand="1"
             xmlns="http://schemas.xmlsoap.org/ws/2002/12/secext">
              <UsernameToken wsu:Id="id">
                <Username>%s</Username>
                <Password>%s</Password>
              </UsernameToken>
            </Security>
            <Timestamp SOAP-ENV:mustUnderstand="1" Id="id"
             xmlns="http://schemas.xmlsoap.org/ws/2002/07/utility">
              <Created>2037-08-12T14:45:00Z</Created>
              <Expires>2037-08-12T14:45:00Z</Expires>
            </Timestamp>
            <Locale>jp</Locale>
          </SOAP-ENV:Header>
          <SOAP-ENV:Body>
            <ScheduleGetEvents>
        <parameters start="%s" end="%s" all_repeat_events="true">
        </parameters>
            </ScheduleGetEvents>
          </SOAP-ENV:Body>
        </SOAP-ENV:Envelope>
        """

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        username = config.get('garoon', 'user')
        password = config.get('garoon', 'password')
        grn_api_url = config.get('garoon', 'api_url')
        return requests.post(grn_api_url,
                             data=body % (username, password, (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat(), (datetime.datetime.now() + datetime.timedelta(days=day)).isoformat()),
                             headers=headers).text

    def __parse_to_list(self, res):
        tasks = []
        elem = fromstring(res)
        for e in elem.findall(".//schedule_event"):
            if e.get('event_type') == 'normal':
                for child in e.getchildren():
                    if child.tag.endswith('members'):
                        members = child
                    elif child.tag.endswith('when'):
                        when = child.getchildren()[0]
                task = {}

                for member in members.getchildren():
                    if member.getchildren()[0].tag.endswith('facility'):
                       task['location'] = member.getchildren()[0].get('name')
                
                task['start'] = when.get('start')
                task['end'] = when.get('end')
                task['id'] = e.get('id')
                task['detail'] = e.get('detail')
                task['description'] = e.get('description')

                if task['start'] == task['end']:
                   task['all_day'] = True
                else:
                    task['all_day'] = False
                tasks.append(task)
            elif e.get('event_type') == 'banner' or e.get('event_type') == 'allday':
                for child in e.getchildren():
                    if child.tag.endswith('members'):
                        members = child
                    elif child.tag.endswith('when'):
                        when = child.getchildren()[0]
                task = {}
                task['start'] = when.get('start')
                task['end'] = when.get('end')
                task['id'] = e.get('id')
                task['detail'] = e.get('detail')
                task['description'] = e.get('description')
                task['all_day'] = True
                tasks.append(task)
            else:
                task = {}
                task['id'] = e.get('id')
                task['detail'] = e.get('detail')
                task['description'] = e.get('description')
                task['all_day'] = False
                for child in e.getchildren():
                    if child.tag.endswith('members'):
                        members = child
                    elif child.tag.endswith('repeat_info'):
                        repeat_info = child
                for member in members.getchildren():
                    if member.getchildren()[0].tag.endswith('facility'):
                       task['location'] = member.getchildren()[0].get('name')
                

                ## RRULE
                ## event.add('rrule', {'freq': 'yearly', 'bymonth': 10, 'byday': '-1su'})
                ## <condition type="week" day="26" week="4" start_date="2014-01-01" end_date="2014-01-29" start_time="13:00:00" end_time="14:00:00"/>
                condition1 = repeat_info.getchildren()[0]
                rrule = {}
                if condition1.get('type') == 'week':
                    rrule['freq'] = 'weekly'
                    dayofweek = ['SU', 'MO','TU','WE','TH','FR','SA']
                    rrule['byday'] = dayofweek[int(condition1.get('week'))]
                    rrule['until'] = dateutil.parser.parse(condition1.get('end_date')).date()

                    delta = int(condition1.get('week')) - datetime.datetime.now().weekday() - 1
                    start_date = (datetime.datetime.now() + datetime.timedelta(days=delta)).date()
                    task['start'] = start_date.isoformat() + 'T' + condition1.get('start_time')
                    task['end']  = start_date.isoformat() + 'T' + condition1.get('end_time')
                elif condition1.get('type') == 'weekday':
                    rrule['freq'] = 'daily'
                    rrule['until'] = dateutil.parser.parse(condition1.get('end_date')).date()
                    rrule['byday'] = ['MO','TU','WE','TH','FR']
                    task['start'] = condition1.get('start_time')
                    task['end']  = condition1.get('end_time')
                task['rrule'] = rrule

                ## EXDATE
                exclude_info = repeat_info.getchildren()[1]
                exdate = []
                for exclude in exclude_info.getchildren():
                    start_date = exclude.get('start').split('T')[0]
                    exdate.append('%sT%s' % (start_date, condition1.get('start_time')))
                task['exdate'] = exdate
                
                tasks.append(task)
        return tasks
    
    def get_schedule(self, day=14):
        return self.__parse_to_list(self.__get_xml(day))


class ical():
    def to_ical(self, tasks):
        from icalendar import Calendar, Event
        ical = Calendar()
        ical.add('version', '2.0')
        ical.add('prodid', '-//test//hoge//EN')

        for task in tasks:
            event = Event()
            event.add('summary', task['detail'])
            event.add('description', task['description'])
            config = SafeConfigParser()
            config.read('grn2ical.conf')
            grn_url = config.get('garoon', 'view_url')
            event.add('url', '%s/schedule/view?event=%s' % (grn_url, task['id']))
            if task['all_day'] == True:
                event.add('dtstart', dateutil.parser.parse(task['start']).date())
                event.add('dtend', dateutil.parser.parse(task['end']).date())
            else:
                event.add('dtstart', dateutil.parser.parse(task['start']))
                event.add('dtend', dateutil.parser.parse(task['end']))
            if 'rrule' in task.keys():
                event.add('rrule', task['rrule'])
            if 'exdate' in task.keys():
                for exdate in task['exdate']:
                    event.add('exdate', dateutil.parser.parse(exdate))
            if 'location' in task.keys():
                event.add('location', task['location'])
            ical.add_component(event)
        return ical.to_ical()
        

class MyHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        grn = garoon()
        cal = ical()
        tasks = grn.get_schedule()
        body = cal.to_ical(tasks)
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-length', len(body))
        self.end_headers()
        self.wfile.write(body
)
if __name__ == "__main__":
    host = 'localhost'
    port = 8000
    httpd = HTTPServer((host, port), MyHandler)
    print('serving at port', port)
    httpd.serve_forever()

    
