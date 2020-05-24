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

QUIZ_REQ_FIELDS = ['id','title','description','quiz_type',
                   'assignment_group_id','time_limit','shuffle_answers',
                   'hide_results','show_correct_answers',
                   'show_correct_answers_at','hide_correct_answers_at',
                   'show_correct_answers_last_attempt','allowed_attempts',
                   'scoring_policy','one_question_at_a_time','cant_go_back',
                   'access_code','ip_filter','due_at','lock_at','unlock_at',
                   'published','one_time_results',
                   'only_visible_to_overrides']
GROUP_REQ_FIELDS = ['id','name','pick_count','question_points',
                    'assessment_question_bank_id']
QUESTION_REQ_FIELDS = ['id','question_name','question_text','quiz_group_id',
                       'question_type','position','points_possible',
                       'correct_comments','incorrect_comments',
                       'neutral_comments','text_after_answers','answers']

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("-f", "--canvas-token-file", type=argparse.FileType('r'),
                   help="File containing the Canvas token used for authentication")
group.add_argument("-t", "--canvas-token",
                   help="Canvas token used for authentication")
parser.add_argument("json_file",
                    help="JSON file, may be an input file (for pushing), an oautput file (for loading), or both (for sync).")
parser.add_argument("-c", "--course", type=int, help="Course ID")
parser.add_argument("-q", "--quiz", type=int, help="Quiz ID")
parser.add_argument("-p", "--push-quiz", action='store_true',
                    help="Push JSON values to Canvas")
parser.add_argument("-l", "--load-quiz", action='store_true',
                    help="Load JSON from values retrieved from Canvas")
parser.add_argument("-s", "--strip", action='store_true',
                    help="Strip from output JSON values that cannot be pushed back in updates.")
parser.add_argument("-d", "--debug", help="Enable debugging mode",
                    action='store_true')
args = parser.parse_args()

if args.canvas_token_file:
    args.canvas_token = args.canvas_token_file.read().strip()
    args.canvas_token_file.close()
canvas = canvas.Canvas(args.canvas_token)

if args.push_quiz and args.load_quiz:
    json_file = open(args.json_file, mode='r+')
elif args.push_quiz:
    json_file = open(args.json_file, mode='r')
elif args.load_quiz:
    json_file = open(args.json_file, mode='w')
else:
    parser.error('Action missing, must select -p, -l or both.')

if args.push_quiz:
    print('Reading JSON file...')
    values_from_json = json.load(json_file)
    if not args.quiz and 'quiz' in values_from_json and \
       'id' in values_from_json['quiz']:
        args.quiz = values_from_json['quiz']['id']
else:
    values_from_json = {}    

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

if 'quiz' in values_from_json:
    print('Pushing updates to quiz...')
    quiz = canvas.update_quiz(course, quiz['id'], values_from_json['quiz'])

groups_from_file = {}
if 'groups' in values_from_json:
    print('Pushing updates to question groups...')
    for (group_id, group) in values_from_json['groups'].items():
        existing_id = None
        try:
            if int(group_id) in groups: existing_id = int(group_id)
        except:
            pass
        group = canvas.update_question_group(course, quiz, existing_id,
                                             group)['quiz_groups'][0]
        groups_from_file[group_id] = group
        groups[group['id']] = group

if 'questions' in values_from_json:
    print('Pushing updates to questions...')
    for (question_id, question) in values_from_json['questions'].items():
        pass
        if question['quiz_group_id'] in groups_from_file:
            question['quiz_group_id'] = groups_from_file[question['quiz_group_id']]['id']
        existing_id = None
        try:
            if int(question_id) in questions: existing_id = int(question_id)
        except:
            pass
        question = canvas.update_question(course, quiz, existing_id, question)
        questions[question['id']] = question

if args.strip:
    quiz      = {k:v for k, v in quiz.items()
                 if k in QUIZ_REQ_FIELDS}
    groups    = {id:{k:v for k,v in group.items()
                     if k in GROUP_REQ_FIELDS}
                 for id, group in groups.items()}
    questions = {id:{k:v for k,v in question.items()
                     if k in QUESTION_REQ_FIELDS}
                 for id, question in questions.items()}

if args.load_quiz:
    print('Saving values back to JSON file...')
    json_file.seek(0)
    json.dump({ 'quiz': quiz,
                'groups': groups,
                'questions': questions
    }, json_file, indent=2, sort_keys=True)
    json_file.truncate()

json_file.close()
print('\nDONE.')
