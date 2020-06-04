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
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("-f", "--canvas-token-file", type=argparse.FileType('r'),
                   help="File containing the Canvas token used for authentication")
group.add_argument("-t", "--canvas-token",
                   help="Canvas token used for authentication")
parser.add_argument("-c", "--course", type=int, help="Course ID")
parser.add_argument("-a", "--assignment", type=int, help="Assignment ID")
parser.add_argument("-p", "--parts", help="CSV file with assignment parts")
parser.add_argument("-m", "--marks", help="CSV file with assignment marks")
parser.add_argument("-d", "--debug", help="Enable debugging mode",
                    action='store_true')
args = parser.parse_args()

if args.canvas_token_file:
    args.canvas_token = args.canvas_token_file.read().strip()
    args.canvas_token_file.close()
canvas = canvas.Canvas(args.canvas_token)

print('Reading data from Canvas...')

course = None
if args.course:
    course = canvas.course(args.course)
if course == None:
    courses = canvas.courses()
    for index, course in enumerate(courses):
        print("%2d: %7d - %10s / %s" %
              (index, course['id'], course['term']['name'],
               course['course_code']))
    
    course_index = int(input('Which course? '))
    course = courses[course_index]

print('Using course: %s / %s' % (course['term']['name'],
                                 course['course_code']))

# Reading assignment list
assignment = None
if args.assignment:
    assignment = canvas.assignment(course, args.assignment)

if assignment == None:
    assignments = canvas.assignments(course)
    for index, assignment in enumerate(assignments):
        print("%2d: %7d - %s" % (index, assignment['id'],
                                 assignment['name']))
        
    asg_index = int(input('Which assignment? '))
    assignment = assignments[asg_index]

print('Using assignment: %s' % (assignment['name']))

# Reading students
students = canvas.students(course)

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
                    'points': round(float(p['Weight']) * 100,2),
                }}
            }
            last = i
        criteria[last+1] = {
            'id': 'PENALTY',
            'description': 'Penalties',
            'long_description': 'Penalties, including late penalties.',
            'ratings': {0: {'points': 0}}
        }

        canvas.update_rubric(course, assignment, {
            'title': assignment['name'],
            'free_form_criterion_comments': '1',
            'criteria': criteria
        })

if args.marks:
    assignment = canvas.assignment(course, assignment['id'])
    
    with open(args.marks, 'r', newline='') as file:
        marks = csv.DictReader(file)
        i = 0
        for mark in marks:
            i += 1
            print('Pushing grade %d...' % i, end='\r');
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
                rubpoints = round(float(mark[rub['id']]) * rub['points'],2) \
                            if rub['id'] in mark else 0
                rubcomments = mark['Comments__' + rub['id']] \
                              if 'Comments__' + rub['id'] in mark else None
                totalcalc += rubpoints
                assess[rub['id']] = {'points': rubpoints,
                                     'comments': rubcomments}
            penalty = round(penaltypc * totalcalc / 100.0,2)
            # TODO Ensure total == totalcalc - penalty within a tolerance
            assess['PENALTY'] = {
                'points': -penalty,
                'comments': penaltyreason
            }
            # TODO General comments
            canvas.send_assig_grade(course, assignment, student, assess)
            
print('\nDONE.')
