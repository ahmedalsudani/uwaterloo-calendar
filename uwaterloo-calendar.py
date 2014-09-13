from flask import Flask, Response
from hammock import Hammock
from os import environ
from json import loads as read_json
import re
from icalendar import Calendar, Event
import datetime
from pytz import timezone

app = Flask(__name__)

KEY = environ.get('UWATERLOO_KEY')
uwaterloo = Hammock('https://api.uwaterloo.ca/v2')
params = {'key': KEY}
tz = timezone('Canada/Eastern')

DAYS_NUMBERED = {
    'M': 0,
    'T': 1,
    'W': 2,
    'Th': 3,
    'F': 4
}
TERM_START = datetime.date(2014, 9, 8)
TERM_END = datetime.date(2014, 12, 2)
COURSE_FIELDS = ['catalog_number', 'subject', 'section']
SECTION_FIELDS = ['instructors', 'location']
DATE_FIELDS = ['weekdays', 'start_time', 'end_time']


# Per http://stackoverflow.com/a/6558571
def next_weekday(d, weekday):
    days_ahead = weekday - d.weekday()
    if days_ahead < 0:  # Target day already happened this week
        days_ahead += 7
    return d + datetime.timedelta(days_ahead)


def split_days(raw_days, day_map=DAYS_NUMBERED):
    day_codes = re.findall(r'[A-Z][a-z]?', raw_days)
    days = [day_map[i] for i in day_codes]
    return days


def parse_instructors(instructors):
    parsed = []
    for i in instructors:
        last_name, first_name = i.split(',')
        first_initial = first_name[0]
        parsed.append('%(first_initial)s. %(last_name)s' % locals())
    return parsed


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

    c['days_numbered'] = split_days(c['weekdays'], day_map=DAYS_NUMBERED)
    c['start_hour'] = int(re.search(r'^\d+', c['start_time']).group())
    c['end_hour'] = int(re.search(r'^\d+', c['end_time']).group())
    c['start_minute'] = int(re.search(r'\d+$', c['start_time']).group())
    c['end_minute'] = int(re.search(r'\d+$', c['end_time']).group())
    c['parsed_instructors'] = parse_instructors(c['instructors'])
    c['instructor'] = c['parsed_instructors'][0]
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
            e['summary'] = '%(subject)s %(catalog_number)s %(instructor)s %(section)s' % c
            e['description'] = 'Instructors: ' + str(c['instructors'])
            e['location'] = c['location']['building'] + ' ' + c['location']['room']
            first_class = next_weekday(TERM_START, day)
            e.add('dtstart', tz.localize(datetime.datetime.combine(first_class, datetime.time(c['start_hour'], c['start_minute']))))
            e.add('dtend', tz.localize(datetime.datetime.combine(first_class, datetime.time(c['end_hour'], c['end_minute']))))
            e['uid'] = ('1149' + c['subject'] + c['catalog_number'] + c['section'] +
                        'day' + str(day) + 'v0.0.1').replace(r' ', '-')
            e.add('rrule', {'freq': 'weekly', 'until': TERM_END})
            cal.add_component(e)
    return cal.to_ical()


@app.route('/ics/<classes>')
def ics(classes):
    class_list = parse_classes(classes)
    schedule = []

    for c in class_list:
        schedule += schedule_by_classnum(c)

    class_info = map(extract_class_info, schedule)

    calendar = create_calendar(class_info)

    response = Response(response=calendar,mimetype='text/calendar',
                        headers={'Content-Disposition': 'attachment; filename=calendar.ics'})
    return response

@app.route('/')
def home():
    return "Hi"

if __name__ == '__main__':
    app.run(debug=True)
