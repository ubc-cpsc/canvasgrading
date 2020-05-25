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
from collections import OrderedDict

import canvas

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("-f", "--canvas-token-file", type=argparse.FileType('r'),
                   help="File containing the Canvas token used for authentication")
group.add_argument("-t", "--canvas-token",
                   help="Canvas token used for authentication")
parser.add_argument("-c", "--course", type=int, help="Course ID")
parser.add_argument("-q", "--quiz", type=int, help="Original Quiz ID")
parser.add_argument("--practice", action='store_true',
                    help="Change quiz to be a practice quiz")
parser.add_argument("--published", action='store_true',
                    help="By default, new quiz is set to unpublished. This option sets it as published.")
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

# Reading questions
print('Retrieving quiz questions...')
questions = OrderedDict(sorted(canvas.questions(course, quiz, include_groups=True).items()))

print('Retrieving quiz question groups...')
groups = OrderedDict(sorted({g['id']: g for g in [
    question['quiz_group_full'] for question in questions.values()
    if 'quiz_group_full' in question] }.items()))

if args.practice:
    quiz['quiz_type'] = 'practice_quiz'
    quiz['unlock_at'] = quiz['lock_at']
    quiz['due_at'] = None
    quiz['lock_at'] = None
    quiz['allowed_attempts'] = -1
    quiz['time_limit'] = None
    quiz['show_correct_answers'] = True
    quiz['show_correct_answers_at'] = None
    quiz['title'] += ' (Practice Version)'
else:
    quiz['title'] += ' (copy)'
quiz['published'] = args.published

print('Creating new quiz...')
new_quiz = canvas.update_quiz(course, None, quiz)

new_groups = {}
print('Pushing question groups...')
for (group_id, group) in groups.items():
    group = canvas.update_question_group(course, new_quiz, None,
                                         group)['quiz_groups'][0]
    new_groups[group_id] = group

new_questions = {}
print('Pushing questions...')
for (question_id, question) in questions.items():
    if question['quiz_group_id'] in new_groups:
        question['quiz_group_id'] = new_groups[question['quiz_group_id']]['id']
    question = canvas.update_question(course, new_quiz, None, question)
    new_questions[question['id']] = question

print('\nDONE. New quiz: ')
print('\tTitle: %s' % new_quiz['title'])
print('\tURL  : %s' % new_quiz['html_url'])
