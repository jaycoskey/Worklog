#!/usr/bin/env python

import argparse
import datetime as dt
import pprint
import re
# from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml import YAML as yaml_loader_factory
import sys


class Tag:
    DATE = 'date'
    DATES = 'dates'
    EVENT = 'event'
    EVENTS = 'events'
    ID = 'id'
    LUNCH = 'lunch'
    NAME = 'name'
    NOTE = 'note'
    NOTES = 'notes'
    PEOPLE = 'people'
    PERSON = 'person'
    PROJECT = 'project'
    PROJECTS = 'projects'
    TEXT = 'text'
    URL = 'url'
    URLS = 'urls'
    WHERE = 'where'


class WorkLog:
    def __init__(self, data=None):
        self.dates = []
        self.people = []
        self.projects = []

        if data:
            for k, v in data.items():
                if k == Tag.DATES:
                    for date, dinfo in v.items():
                        date_obj = WLDate(str(date), dinfo)
                        self.add_date(date_obj)
                elif k == Tag.PEOPLE:
                    for person_map in v:
                        person = WLPerson(person_map)
                        self.add_person(person)
                elif k == Tag.PROJECTS:
                    for project_map in v:
                        project = WLProject(project_map)
                        self.add_project(project)

    def __str__(self):
        dates_str = ('\n'.join([str(date) for date in self.dates])
                    if self.dates
                    else '<None>'
                    )
        people_str = ('\n'.join([str(person) for person in self.people])
                     if self.people
                     else '<None>'
                     )
        projects_str = ('\n'.join([str(project) for project in self.projects])
                       if self.projects
                       else '<None>'
                       )
        result = ( '---\n'
                 + f'{Tag.DATES}:\n{dates_str}\n'
                 + f'{Tag.PEOPLE}:\n{people_str}\n'
                 + f'{Tag.PROJECTS}:\n{projects_str}\n'
                 )
        return result

    def add_date(self, date):
        self.dates.append(date)

    def add_person(self, person):
        self.people.append(person)

    def add_project(self, project):
        self.projects.append(project)

    def check_constraints(self):
        self.check_people()
        self.check_projects()

    def check_people(self):
        people_ids = set([person.id for person in self.people if person.id])
        person_pattern = re.compile('@(\w+)')
        people_refs = set([txt for note in self.text_generator()
                               for txt in re.findall(person_pattern, note)
                               ])
        bad_refs = people_refs.difference(people_ids)
        if bad_refs:
            for bad_ref in bad_refs:
                print(f'Undefined person: {bad_ref}')
            raise ValueError(bad_refs)

    def check_projects(self):
        project_ids = [project.id for project in self.projects if project.id]
        project_pattern = re.compile('#(\w+)')
        project_refs = set([txt for note in self.text_generator()
                                for txt in re.findall(project_pattern, note)
                                ])
        bad_refs = project_refs.difference(project_ids)
        if bad_refs:
            for bad_ref in bad_refs:
                print(f'Undefined project: {bad_ref}')
            raise ValueError(bad_refs)

    def print_date_refs(self):
        date_strs = set([date.date_str for date in self.dates])
        date_pattern = re.compile('\!(\d{4}-\d{2}-\d{2})')
        date_refs = set([txt for note in self.text_generator()
                             for txt in re.findall(date_pattern, note)
                             ])
        print('Date strs: ' + '; '.join(date_strs))
        print('Date refs: ' + '; '.join(date_refs))

    def text_generator(self):
        for date in self.dates:
            if date.lunch and date.lunch.notes:
                for note in date.lunch.notes:
                    yield note
        for person in self.people:
            for event in person.events:
                yield event.text
            for note in person.notes:
                yield note
        for project in self.projects:
            for event in project.events:
                yield event.text
            for note in project.notes:
                yield note


class WLDate:
    def __init__(self, date_str, cm):
        assert_type(date_str, 'str')
        assert_type(cm, 'CommentedMap')
        # print('INFO: Date typecheck passed')
        self.date_str = date_str
        if Tag.LUNCH in cm:
            self.lunch = WLLunch(cm['lunch'])
        else:
            self.lunch = Nothing

        self.notes = []
        if Tag.NOTES in cm:
            for note_info in cm[Tag.NOTES]:
                txt = note_info[Tag.NOTE]
                assert_type(txt, 'str')
                self.notes.append(txt)

    def __str__(self):
        note_str = lambda note: f'      - {Tag.NOTE}: {note}'
        result = ( f'  {self.date_str}:\n'
                 + (str(self.lunch) if self.lunch else '')
                 + (f'    {Tag.NOTES}:\n' if self.notes else '')
                 + ('\n'.join([note_str(note) for note in self.notes])
                     if self.notes else ''
                     )
                 )
        return result

    def day_of_week(self):
        def zellers_algo(y, m, d):
            if m == 1 or m == 2:
                m += 12
                y -= 1
            c = int(y/100)
            y2 = y % 100
            tmp = d + int(13*(m+1)/5) + y2 + int(y2/4) + int(c/4) - 2*c
            index = tmp % 7
            days = 'Sat Sun Mon Tue Wed Thu Fri'.split()
            return days[index]

        y, m, d = list(map(lambda s: int(s), self.date_str.split('-')))
        day = zellers_algo(y, m, d)
        print(f'Day of week of {self.date_str} is {day}')


class WLEvent:
    def __init__(self, cm):
        assert_type(cm, 'CommentedMap')
        # print('INFO: Event typecheck passed')
        if 'date' in cm:
            self.date_str = str(cm[Tag.DATE])
        else:
            self.date_str = '<Unknown>'

        if Tag.TEXT in cm:
            self.text = str(cm[Tag.TEXT])
        else:
            self.text = '<None>'

    def __str__(self):
        return ( f'        {Tag.DATE}: {self.date_str}\n'
               + f'        {Tag.TEXT}: |-\n'
               + f'          {self.text}'
               )


class WLLunch:
    def __init__(self, cm):
        assert_type(cm, 'CommentedMap')
        # print('INFO: Lunch typecheck passed')
        if Tag.WHERE in cm:
            self.where = cm[Tag.WHERE]
        else:
            self.where = None

        self.people_strs = []
        if Tag.PEOPLE in cm:
            assert_type(cm[Tag.PEOPLE], 'CommentedSeq')
            for person_info in cm[Tag.PEOPLE]:
                self.people_strs.append(person_info[Tag.PERSON])

        self.notes = []
        if 'notes' in cm:
            assert_type(cm[Tag.NOTES], 'CommentedSeq')
            for note_info in cm[Tag.NOTES]:
                assert_type(note_info, 'CommentedMap')
                txt = note_info[Tag.NOTE]
                assert_type(txt, 'str')
                self.notes.append(txt)

    def __str__(self):
        where_str = f'      {Tag.WHERE}: {self.where}\n' if self.where else ''
        people_str = (f'      {Tag.PEOPLE}:\n'
                     + '\n'.join([f'        - {Tag.PERSON}: {person_str}'
                                     for person_str in self.people_strs
                                 ]) + '\n'
                     ) if self.people_strs else ''
        notes_str = (f'      {Tag.NOTES}:\n'
                    + '\n'.join([f'        - {Tag.NOTE}: {note}'
                                    for note in self.notes])
                    + '\n'
                    ) if self.notes else ''
        result = ( f'    {Tag.LUNCH}:\n'
                 + where_str
                 + people_str
                 + notes_str
                 )
        return result


class WLPerson:
    def __init__(self, cm):
        assert_type(cm, 'CommentedMap')
        # print('INFO: Person typecheck passed')
        if Tag.ID in cm:
            self.id = cm[Tag.ID]
        else:
            self.id = Nothing

        if 'name' in cm:
            self.name = cm[Tag.NAME]
        else:
            self.name = '<None>'

        self.events = []
        if Tag.EVENTS in cm:
            assert_type(cm[Tag.EVENTS], 'CommentedSeq')
            for event_info in cm[Tag.EVENTS]:
                self.events.append(WLEvent(event_info))

        self.notes = []
        assert_type(cm[Tag.NOTES], 'CommentedSeq')
        for note_info in cm[Tag.NOTES]:
            self.notes.append(note_info[Tag.NOTE])

    def __str__(self):
        event_str = lambda event: f'      - {Tag.EVENT}:\n{str(event)}\n'
        events_str = (f'    {Tag.EVENTS}:\n'
                    + '\n'.join([event_str(event) for event in self.events])
                    ) if self.events else ''
        note_str = lambda note: f'      - {Tag.NOTE}: {note}'
        notes_str = (f'    {Tag.NOTES}:\n'
                    + '\n'.join([note_str(note) for note in self.notes])
                    ) if self.notes else ''
        result = (f'  - {Tag.PERSON}:\n'
                 + (f'    {Tag.ID}: {self.id}\n' if self.id else '')
                 + (f'    {Tag.NAME}: {self.name}\n' if self.name else '')
                 + events_str
                 + notes_str
                 )
        return result


class WLProject:
    def __init__(self, cm):
        assert_type(cm, 'CommentedMap')
        # print('INFO: Project typecheck passed')
        for k in cm.keys():
            print(f'INFO: Project key={k}')
        if Tag.ID in cm:
            self.id = cm[Tag.ID]

        if Tag.NAME in cm:
            self.name = cm['name']
        else:
            self.name = '<None>'

        if Tag.TEXT in cm:
            self.text = cm[Tag.TEXT]
        else:
            self.text = None

        self.events = []
        if Tag.EVENTS in cm:
            assert_type(cm[Tag.EVENTS], 'CommentedSeq')
            for event_info in cm[Tag.EVENTS]:
                self.events.append(WLEvent(event_info))

        self.people_strs = []
        if Tag.PEOPLE in cm:
            assert_type(cm[Tag.PEOPLE], 'CommentedSeq')
            for person_info in cm[Tag.PEOPLE]:
                self.people_strs.append(person_info[Tag.PERSON])

        self.urls = []
        if Tag.URLS in cm and cm[Tag.URLS]:
            assert_type(cm[Tag.URLS], 'CommentedSeq')
            for url_info in cm[Tag.URLS]:
                self.urls.append(url_info[Tag.URL])

        self.notes = []
        if Tag.NOTES in cm:
            assert_type(cm[Tag.NOTES], 'CommentedSeq')
            for note_info in cm[Tag.NOTES]:
                self.notes.append(note_info[Tag.NOTE])

    def __str__(self):
        event_str = lambda event: f'      - {Tag.EVENT}:\n{str(event)}'
        events_str = (f'    {Tag.EVENTS}:\n'
                    + '\n'.join([event_str(event) for event in self.events])
                    + '\n'
                    ) if self.events else ''
        person_str = lambda pstr: f'      - {Tag.PERSON}: {pstr}'
        people_str = (f'    {Tag.PEOPLE}:\n'
                    + '\n'.join([person_str(pstr) for pstr in self.people_strs])
                    + '\n'
                    ) if self.people_strs else ''
        url_str = lambda url: f'      - {Tag.URL}: {url}'
        urls_str = (f'    {Tag.URLS}:\n'
                    + '\n'.join([url_str(url) for url in self.urls])
                    + '\n'
                    ) if self.urls else ''
        note_str = lambda note: f'      - {Tag.NOTE}: {note}'
        notes_str = (f'    {Tag.NOTES}:\n'
                    + '\n'.join([note_str(note) for note in self.notes])
                    ) if self.notes else ''

        result = (  f'  - {Tag.PROJECT}:\n'
                 + (f'    {Tag.ID}: {self.id}\n' if self.id else '')
                 + (f'    {Tag.NAME}: {self.name}\n' if self.name else '')
                 + (f'    {Tag.TEXT}: {self.text}\n' if self.text else '')
                 + events_str
                 + people_str
                 + urls_str
                 + notes_str
                 )
        return result


def assert_type(arg, type_name):
    if type(arg).__name__ == type_name:
        return
    else:
        raise ValueError(f'type(arg) = {type(arg)} != {type_name}')


def main():
    DEFAULT_INPUT_FILE = 'worklog.yaml'

    parser = argparse.ArgumentParser(description='Read in worklog (YAML) file, and print out query result')
    parser.add_argument('-i', '--infile')
    args = parser.parse_args()

    infile = DEFAULT_INPUT_FILE
    if args.infile and args.infile != '':
        infile = args.infile

    yaml_loader = yaml_loader_factory()
    with open(infile) as f:
        data = yaml_loader.load(f)

    wlog = WorkLog(data)
    wlog.check_constraints()
    print(wlog)


if __name__ == '__main__':
    main()

