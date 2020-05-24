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

MAIN_URL = 'https://canvas.ubc.ca/api/v1'

def end_file(htmlfile):
    htmlfile.write('</body>\n</html>')
    htmlfile.close()

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("-f", "--canvas-token-file", type=argparse.FileType('r'),
                   help="File containing the Canvas token used for authentication")
group.add_argument("-t", "--canvas-token",
                   help="Canvas token used for authentication")
parser.add_argument("-o", "--output",
                    help="Output file")
parser.add_argument("-c", "--course", type=int, help="Course ID")
parser.add_argument("-q", "--quiz", type=int, help="Quiz ID")
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

# Reading quiz list
quiz = None
if args.quiz:
    quiz = canvas.quiz(course, args.quiz)

if quiz == None:
    quizzes = canvas.quizzes(course)
    for index, quiz in enumerate(quizzes):
        print("%2d: %7d - %s" % (index, quiz['id'], quiz['title']))
        
    quiz_index = int(input('Which quiz? '))
    quiz = quizzes[quiz_index]

print('Using quiz: %s' % (quiz['title']))

if not args.output:
    args.output = '%s.json' % re.sub(r'[^A-Za-z0-9-_]+', '', quiz['title'])
    print('Output file: %s' % args.output);

# Reading questions
print('Retrieving quiz questions...')
questions = canvas.questions(course, quiz)

print('Retrieving quiz question groups...')
groups = {}
for group_id in [q['quiz_group_id'] for q in questions.values()]:
    if group_id:
        groups[group_id] = canvas.question_group(course, quiz, group_id)

print('Generating JSON file...')

with open(args.output, 'w') as file:
    data = {}
    data['quiz'] = quiz
    data['groups'] = groups
    data['questions'] = questions
    json.dump(data, file, indent=2)

print('\nDONE.')
