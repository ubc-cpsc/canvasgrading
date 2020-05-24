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
parser.add_argument("input", type=argparse.FileType('r'),
                    help="Input file")
parser.add_argument("-c", "--course", type=int, help="Course ID")
parser.add_argument("-q", "--quiz", type=int, help="Quiz ID")
parser.add_argument
parser.add_argument("-d", "--debug", help="Enable debugging mode",
                    action='store_true')
args = parser.parse_args()

if args.canvas_token_file:
    args.canvas_token = args.canvas_token_file.read().strip()
    args.canvas_token_file.close()
canvas = canvas.Canvas(args.canvas_token)

print('Reading JSON file...')
updated = json.load(args.input)
if not args.quiz and 'quiz' in updated and 'id' in updated['quiz']:
    args.quiz = updated['quiz']['id']

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

# Reading questions
print('Retrieving current quiz questions...')
questions = canvas.questions(course, quiz)

print('Retrieving current quiz question groups...')
groups = {}
for group_id in [q['quiz_group_id'] for q in questions.values()]:
    if group_id:
        groups[group_id] = canvas.question_group(course, quiz, group_id)

if 'quiz' in updated:
    print('Pushing updates to quiz...')
    quiz = canvas.update_quiz(course, quiz['id'], updated['quiz'])

if 'groups' in updated:
    print('Pushing updates to question groups...')
    for (group_id, group) in updated['groups'].items():
        existing_id = None
        try:
            if int(group_id) in groups: existing_id = int(group_id)
        except:
            pass
        groups[group_id] = canvas.update_question_group(course, quiz,
                                                        existing_id,
                                                        group)

if 'questions' in updated:
    print('Pushing updates to questions...')
    for (question_id, question) in updated['questions'].items():
        pass
        if question['quiz_group_id'] and \
           str(question['quiz_group_id']) in groups:
            question['quiz_group_id'] = groups[question['quiz_group_id']]['id']
        existing_id = None
        try:
            if int(question_id) in questions: existing_id = int(question_id)
        except:
            pass
        questions[question_id] = canvas.update_question(course, quiz,
                                                        existing_id,
                                                        question)

print('\nDONE.')
