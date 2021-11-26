#! /usr/bin/python3

import os
import csv
import re
from os import path
import json
import requests
import weasyprint
import zipfile
import argparse

import canvas

parser = argparse.ArgumentParser()
canvas.Canvas.add_arguments(parser, assignment=True)
parser.add_argument("-p", "--parts", help="CSV file with assignment parts")
parser.add_argument("-m", "--marks", help="CSV file with assignment marks")
args = parser.parse_args()
canvas = canvas.Canvas(args=args)

print('Reading data from Canvas...')
course = canvas.course(args.course, prompt_if_needed=True)
print('Using course: %s / %s' % (course['term']['name'],
                                 course['course_code']))

assignment = course.assignment(args.assignment, prompt_if_needed=True)
print('Using assignment: %s' % (assignment['name']))

# Reading students
students = course.students()

# Reading parts CSV file
if args.parts:
    with open(args.parts, 'r', newline='') as file:
        parts = csv.DictReader(file)
        if 'Part' not in parts.fieldnames or \
           'Weight' not in parts.fieldnames:
            raise ValueError('Parts file does not contain ID or weight.')
        if 'Description' not in parts.fieldnames:
            print('WARNING: parts file does not contain descriptions.')

        criteria = {}
        last = 0
        for (i, p) in enumerate(parts):
            criteria[i] = {
                'id': p['Part'],
                'description': p['Short'] if 'Short' in p and p['Short'] \
                else p['Part'],
                'long_description': p['Description'] if 'Description' in p \
                else None,
                'ratings': {0: {
                    'points': round(float(p['Weight']) * 100, 2),
                }}
            }
            last = i
        criteria[last+1] = {
            'id': 'PENALTY',
            'description': 'Penalties',
            'long_description': 'Penalties, including late penalties.',
            'ratings': {0: {'points': 0}}
        }

        assignment.update_rubric({
            'title': assignment['name'],
            'free_form_criterion_comments': '1',
            'criteria': criteria
        })

if args.marks:
    # Update local representation of assignment
    assignment = course.assignment(assignment['id'])
    if 'rubric' not in assignment.data:
        print('ERROR: Assignment has not been set up with a rubric.')
        exit(0)

    with open(args.marks, 'r', newline='') as file:
        marks = csv.DictReader(file)
        i = 0
        for mark in marks:
            i += 1
            print('Pushing grade %d...' % i, end='\r')
            if mark['SID'] not in students:
                print('\nIgnoring student %s, not on Canvas.' % mark['SID'])
                continue
            student = students[mark['SID']]
            total = float(mark['TOTAL']) * 100
            comments = ''
            penaltypc = float(mark['PENALTY']) if 'PENALTY' in mark else 0.0
            penaltyreason = mark['PENALTYREASON'] if 'PENALTYREASON' in mark else ''
            if 'INPROGRESS' in mark:
                comments += '%s\n' % mark['INPROGRESS']
            assess = {}
            totalcalc = 0
            for rub in assignment['rubric']:
                rubpoints = round(float(mark[rub['id']]) * rub['points'], 2) \
                            if rub['id'] in mark else 0
                rubcomments = mark['Comments__' + rub['id']] \
                              if 'Comments__' + rub['id'] in mark else None
                totalcalc += rubpoints
                assess[rub['id']] = {'points': rubpoints,
                                     'comments': rubcomments}
            penalty = round(penaltypc * totalcalc / 100.0, 2)
            # TODO Ensure total == totalcalc - penalty within a tolerance
            assess['PENALTY'] = {
                'points': -penalty,
                'comments': penaltyreason
            }
            # TODO General comments
            assignment.send_assig_grade(student, assess)

print('\nDONE.')
