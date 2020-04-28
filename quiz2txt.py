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

def process_submission(qs):
    answers = {}
    sub_questions = {}
    num_attempts = 0
    
    sub = submissions[qs['submission_id']]
    snum = sub['user']['sis_user_id']
            
    for r in api_request('/quiz_submissions/%d/questions' % qs['id']):
        for q in r['quiz_submission_questions']:
            sub_questions[q['id']] = q
            
    variation = {}
    for attempt in sub['submission_history']:
        if 'submission_data' in attempt:
            num_attempts += 1
            if attempt['attempt'] in variation.keys():
                variation[attempt['attempt']] += 'x'
            else:
                variation[attempt['attempt']] = ''
            for answer in attempt['submission_data']:
                question_id = answer['question_id']
                if question_included(question_id):
                    question = sub_questions[question_id]
                    if question['question_type'] not in ['essay_question', 'file_upload_question']:
                        continue
                    if question_id not in zipfiles:
                        zipfiles[question_id] = zipfile.ZipFile('%s_%s_%d.zip' % \
                                                                (exam_name, question['question_name'], question_id), 'w')
                    zip = zipfiles[question_id]
                    common_substring = '%d_%s_v%d%s' % \
                                       (question_id, snum, attempt['attempt'], variation[attempt['attempt']])
                    # if question['quiz_group_id'] != None:
                    #     common_substring = 'qg%d_%s' % (question['quiz_group_id'], common_substring)
                    if question['question_type'] == 'essay_question':
                        raw_file_name = '%s_answer.html' % common_substring
                        zip.writestr(raw_file_name, '/* %s */\n%s' % \
                                     (question['question_text'], answer['text']))
                    elif question['question_type'] == 'file_upload_question':
                        for attach in answer['attachment_ids']:
                            for file in api_request('/files/%s' % attach):
                                raw_file_name = '%s_upload_%s' % \
                                                (common_substring, file['display_name'])
                                data = requests.get(file['url'])
                                if data:
                                    zip.writestr(raw_file_name, data.content)
                    rubric_file = '%s_rubric.txt' % common_substring
                    template_file = '%s_rubtempl_q%d.txt' % (exam_name, question_id)
                    if not os.path.isfile(template_file) and question['quiz_group_id'] != None:
                        template_file = '%s_rubtempl_qg%d.txt' % \
                                        (exam_name, question['quiz_group_id'])
                    if os.path.isfile(template_file):
                        zip.write(template_file, arcname=rubric_file)
                    else:
                        print('Missing rubric file for question %d (question group %d)' % (question_id, question['quiz_group_id']) )

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

def question_included(qid):
    return len(sys.argv) <= 5 or str(qid) in sys.argv[5]
    
exam_name       = sys.argv[1]
token_file_name = sys.argv[2]

courses = []
quizzes = []
submissions = {}
quiz_submissions = []
zipfiles = {}

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
                            'include[]=user&include[]=submission&'
                            'include[]=submission_history'
                            % (course_id, quiz_id), DEBUG):
    quiz_submissions += response['quiz_submissions']
    for submission in response['submissions']:
        submissions[submission['id']] = submission
    print("Read %d submissions..." % len(quiz_submissions), end='\r');

print('\nGenerating files...')

if DEBUG:
    with open('debug.json', 'w') as file:
        data = {}
        data['quiz'] = quiz
        data['quiz_submissions'] = quiz_submissions
        data['submissions'] = submissions
        json.dump(data, file, indent=2)

num_exams = 0
for qs in quiz_submissions:
    print("Exporting student %d out of %d..." %
          (num_exams + 1, len(quiz_submissions)), end='\r');
    process_submission(qs)
    num_exams += 1

for zip in zipfiles.values():
    zip.close()

print('\nDONE.')
