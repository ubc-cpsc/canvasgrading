#! /usr/bin/python3

import os
import sys
import csv
import textwrap
import re
from os import path
import json
import requests
import weasyprint
import zipfile

MAIN_URL = 'https://canvas.ubc.ca/api/v1'
DEBUG = False # If True, only 10 submissions are processed (useful for testing)

def api_request(request, stopAtFirst = False, debug = False):
    retval = []
    response = requests.get(MAIN_URL + request, headers = token_header)
    while True:
        if (debug): print(response.text)
        retval.append(response.json())
        if stopAtFirst or 'current' not in response.links or \
           'last' not in response.links or \
           response.links['current']['url'] == response.links['last']['url']:
            break
        response = requests.get(response.links['next']['url'],
                                headers = token_header)
    return retval

def send_grade_update(submission_id, attempt, question_id, points, comments):
    data = {'quiz_submissions': [{
        'attempt': attempt,
        'questions': {
            question_id: {'score': points, 'comment': comments}
        }
    }]}
    
    response = requests.put(MAIN_URL + '/courses/%d/quizzes/%d/submissions/%d'
                            % (course_id, quiz_id, submission_id), json = data, headers = token_header)
    print(response.status_code, response.reason, response.text)
    
grades_csv      = sys.argv[1]
token_file_name = sys.argv[2]

courses = []
quizzes = []
grades = []
submissions = {}
quiz_submissions = []
student_sub = {}

print('Loading grades...')

with open(grades_csv, newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    if not all(x in reader.fieldnames for x in \
               ['Question','Student','Attempt','Grade','Comments']):
        raise ValueError('Classlist CSV file must contain at least the following columns: Question,Student,Attempt,Grade,Comments')
    for row in reader:
        grades.append(row)

print('Reading data from Canvas...')

with open(token_file_name) as token_file:
    token = token_file.read().strip()
    token_header = {'Authorization': 'Bearer %s' % token}

# Reading course list
for list in api_request('/courses?include[]=term&state[]=available'):
    courses += list

course = None
if len(sys.argv) > 3:
    for lcourse in courses:
        if str(lcourse['id']) == sys.argv[3]:
            course = lcourse
            break

if course == None:
    for index, course in enumerate(courses):
        print("%2d: %7d - %10s / %s" %
              (index, course['id'], course['term']['name'],
               course['course_code']))
    
    course_index = int(input('Which course? '))
    course = courses[course_index]

course_id = course['id']
print('Using course: %s / %s' % (course['term']['name'],
                                 course['course_code']))

# Reading quiz list
for list in api_request('/courses/%d/quizzes' % course_id):
    quizzes += [quiz for quiz in list if quiz['quiz_type'] == 'assignment']

quiz = None
if len(sys.argv) > 4:
    for lquiz in quizzes:
        if str(lquiz['id']) == sys.argv[4]:
            quiz = lquiz
            break

if quiz == None:
    for index, quiz in enumerate(quizzes):
        print("%2d: %7d - %s" % (index, quiz['id'], quiz['title']))
    quiz_index = int(input('Which quiz? '))
    quiz = quizzes[quiz_index]

quiz_id = quiz['id']
print('Using quiz: %s' % (quiz['title']))

print('Retrieving quiz submissions...')
for response in api_request('/courses/%d/quizzes/%d/submissions?'
                            'include[]=user&include[]=submission'
                            % (course_id, quiz_id), DEBUG):
    quiz_submissions += response['quiz_submissions']
    for submission in response['submissions']:
        submission['quiz_submissions'] = []
        submissions[submission['id']] = submission
        snum = submission['user']['sis_user_id']
        if snum not in student_sub:
            student_sub[snum] = []
        student_sub[snum].append(submission)
    for qs in response['quiz_submissions']:
        sub = submissions[qs['submission_id']]
        sub['quiz_submissions'].append(qs)
    print("Read %d submissions..." % len(quiz_submissions), end='\r');

print('\nSending grades...')

if DEBUG:
    with open('debug.json', 'w') as file:
        data = {}
        data['quiz'] = quiz
        data['quiz_submissions'] = quiz_submissions
        data['submissions'] = submissions
        json.dump(data, file, indent=2)

num_exams = 0
for grade in grades:
    print("Updating grade %d out of %d..." %
          (num_exams + 1, len(grades)), end='\r');

    for sub in student_sub[grade['Student']]:
        for qs in sub['quiz_submissions']:
            if str(qs['attempt']) == grade['Attempt']:
                send_grade_update(qs['id'],
                                  int(grade['Attempt']),
                                  int(grade['Question']),
                                  grade['Grade'],
                                  grade['Comments'])
    
    num_exams += 1

print('\nDONE.')
