from flask import Flask, Response
from hammock import Hammock
from os import environ
from json import loads as read_json, dumps as dump_json
import csv
import re
from icalendar import Calendar, Event
import unicodedata
import datetime


app = Flask(__name__)


KEY = environ.get('UWATERLOO_KEY')
uwaterloo = Hammock('https://api.uwaterloo.ca/v2')
params = {'key': KEY}

DAYS_NUMBERED = {
    'M': 0,
    'T': 1,
    'Th': 2,
    'W': 3,
    'F': 4
}
DAYS = {
    'M': 'Monday',
    'T': 'Tuesday',
    'Th': 'Thursday',
    'W': 'Wednesday',
    'F': 'Friday'
}
TERM_START = '20140908T000000'
TERM_END = '20141201T000000'
COURSE_FIELDS = ['catalog_number', 'subject', 'section']
SECTION_FIELDS = ['instructors', 'location']
DATE_FIELDS = ['weekdays', 'start_time', 'end_time']


# Per http://stackoverflow.com/a/6558571
def next_weekday(d, weekday):
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0: # Target day already happened this week
        days_ahead += 7
    return d + datetime.timedelta(days_ahead)


def split_days(raw_days, map=DAYS):
    day_codes = re.findall(r'[A-Z][a-z]?', raw_days)
    days = [map[i] for i in day_codes]
    return days


def extract_class_info(raw_class):
    course = raw_class
    section = raw_class['classes'][0]
    date = section['date']
    c = dict()
    for i in COURSE_FIELDS:
        c[i] = course[i]
    for i in SECTION_FIELDS:
        c[i] = section[i]
    for i in DATE_FIELDS:
        c[i] = date[i]

    c['days'] = split_days(c['weekdays'])
    c['days_numbered'] = split_days(c['weekdays'], map=DAYS_NUMBERED)
    c['parsed_instructors'] = ""
    for i in c['instructors']:
        c['parsed_instructors'] += i
    return c


def parse_classes(classes):
    list_of_classes = classes.split('+')
    return list_of_classes


def schedule_by_classnum(classnum):
    course = uwaterloo.courses(classnum)('schedule.json')
    response = course.GET(params=params)
    return read_json(response.text)['data']


def create_calendar(classes):
    cal = Calendar()
    cal['dtstart'] = TERM_START
    cal['dtend'] = TERM_END
    for c in classes:
        for day in c['days_numbered']:
            e = Event()
            e['summary'] = c['subject'] + " " + c['catalog_number'] + " " + c['section']
            e['description'] = 'Instructors: ' + c['parsed_instructors']
            e['location'] = c['location']['building']+ c['location']['room']
            first_class = next_weekday(datetime.date(2014, 9, 7), day)
            e['dtstart'] = first_class.strftime('%Y%m%d') + 'T' + c['start_time'].replace(r':','',) + '00'
            e['dtend'] = first_class.strftime('%Y%m%d') + 'T' + c['end_time'].replace(r':','',) + '00'
            e['uid'] = ('1149' + c['subject'] + c['catalog_number'] + c['section'] + 'day' + str(day) + 'v0.0.1').replace(r' ', '-')
            e.add('rrule', {'freq': 'daily'})
            cal.add_component(e)
    return cal.to_ical()



@app.route('/ics/<classes>')
def home(classes):
    class_list = parse_classes(classes)
    schedule = []

    for c in class_list:
        schedule += schedule_by_classnum(c)

    class_info = map(extract_class_info, schedule)

    calendar = create_calendar(class_info)

    response = Response(response=calendar,mimetype='text/calendar', headers={'Content-Disposition': 'attachment; filename=calendar.ics'})
    return response


if __name__ == '__main__':
    app.run(debug=True)
