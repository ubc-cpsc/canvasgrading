#! /usr/bin/python3

import os
import csv
import re
from os import path
import json
import requests
import zipfile
import argparse

MAIN_URL = 'https://canvas.ubc.ca/api/v1'

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
                                                                (args.output_prefix, question['question_name'], question_id), 'w')
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
                    template_file = '%s_rubtempl_q%d.txt' % (args.output_prefix, question_id)
                    if not os.path.isfile(template_file) and question['quiz_group_id'] != None:
                        template_file = '%s_rubtempl_qg%d.txt' % \
                                        (args.output_prefix, question['quiz_group_id'])
                    if os.path.isfile(template_file):
                        zip.write(template_file, arcname=rubric_file)
                    else:
                        print('Missing rubric file for question %d (question group %s)' % (question_id, question['quiz_group_id']) )

def flatten_list(l):
    if isinstance(l, list):
        for x in [x for x in l if isinstance(x, list)]:
            l.remove(x)
            l.extend(x)
    return l
    
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
    if args.not_question and qid in args.not_question:
        return False
    elif args.only_question:
        return qid in args.only_question
    else:
        return True

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("-f", "--canvas-token-file", type=argparse.FileType('r'),
                   help="File containing the Canvas token used for authentication")
group.add_argument("-t", "--canvas-token",
                   help="Canvas token used for authentication")
parser.add_argument("-p", "--output-prefix",
                    help="Path/prefix for output files")
parser.add_argument("-c", "--course", type=int, help="Course ID")
parser.add_argument("-q", "--quiz", type=int, help="Quiz ID")
group = parser.add_mutually_exclusive_group()
group.add_argument("--only-question", action='append', nargs='+', type=int,
                   metavar="QUESTIONID", help="Questions to include")
group.add_argument("--not-question", action='append', nargs='+', type=int,
                   metavar="QUESTIONID", help="Questions to exclude")
parser.add_argument("-d", "--debug", help="Enable debugging mode",
                    action='store_true')
args = parser.parse_args()

flatten_list(args.only_question)
flatten_list(args.not_question)

if args.canvas_token_file:
    args.canvas_token = args.canvas_token_file.read().strip()
    args.canvas_token_file.close()
token_header = {'Authorization': 'Bearer %s' % args.canvas_token}

courses = []
quizzes = []
submissions = {}
quiz_submissions = []
zipfiles = {}

print('Reading data from Canvas...')

# Reading course list
for list in api_request('/courses?include[]=term&state[]=available'):
    courses += list

course = None
if args.course:
    for c in [c for c in courses if c['id'] == args.course]:
        course = c
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
if args.quiz:
    for q in [q for q in quizzes if q['id'] == args.quiz]:
        quiz = q
        break

if quiz == None:
    for index, quiz in enumerate(quizzes):
        print("%2d: %7d - %s" % (index, quiz['id'], quiz['title']))
    quiz_index = int(input('Which quiz? '))
    quiz = quizzes[quiz_index]

quiz_id = quiz['id']
print('Using quiz: %s' % (quiz['title']))

if not args.output_prefix:
    args.output_prefix = re.sub(r'[^A-Za-z0-9-_]+', '', quiz['title'])
    print('Using prefix: %s' % args.output_prefix);

print('Retrieving quiz submissions...')
for response in api_request('/courses/%d/quizzes/%d/submissions?'
                            'include[]=user&include[]=submission&'
                            'include[]=submission_history'
                            % (course_id, quiz_id), args.debug):
    quiz_submissions += response['quiz_submissions']
    for submission in response['submissions']:
        submissions[submission['id']] = submission
    print("Read %d submissions..." % len(quiz_submissions), end='\r');

print('\nGenerating files...')

if args.debug:
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
