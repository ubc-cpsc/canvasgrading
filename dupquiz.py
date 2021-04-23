#!/usr/bin/python3

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
canvas.Canvas.add_arguments(parser, quiz=True)
parser.add_argument("--practice", action='store_true',
                    help="Change quiz to be a practice quiz")
parser.add_argument("--published", action='store_true',
                    help="By default, new quiz is set to unpublished. This option sets it as published.")
args = parser.parse_args()

canvas = canvas.Canvas(args=args)

print('Reading data from Canvas...')
course = canvas.course(args.course, prompt_if_needed=True)
print('Using course: %s / %s' % (course['term']['name'],
                                 course['course_code']))

quiz = course.quiz(args.quiz, prompt_if_needed=True)
print('Using quiz: %s' % (quiz['title']))

# Reading questions
print('Retrieving quiz questions...')
(questions, groups) = quiz.questions()

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
quiz.id = None

print('Creating new quiz...')
quiz.update_quiz()

new_groups = {}
print('Pushing question groups...')
for (group_id, group) in groups.items():
    group = quiz.update_question_group(None, group)['quiz_groups'][0]
    new_groups[group_id] = group

new_questions = {}
print('Pushing questions...')
for (question_id, question) in questions.items():
    if question['quiz_group_id'] in new_groups:
        question['quiz_group_id'] = new_groups[question['quiz_group_id']]['id']
    question = quiz.update_question(None, question)
    questions[question_id] = question
    new_questions[question['id']] = question

print('Updating question order...')
order = []
groups_ordered = set()
for question in questions.values():
    if question['quiz_group_id']:
        if question['quiz_group_id'] not in groups_ordered:
            order.append({'type': 'group',
                          'id': question['quiz_group_id']})
            groups_ordered.add(question['quiz_group_id'])
    else:
        order.append({'type': 'question',
                      'id': question['id']})
quiz.reorder_questions(order)

print('\nDONE. New quiz: ')
print('\tTitle: %s' % quiz['title'])
print('\tURL  : %s' % quiz['html_url'])
