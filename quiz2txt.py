#! /usr/bin/python3

import os
import csv
import re
from os import path
import json
import requests
import zipfile
import argparse
import canvas

def process_submission(qs):
    answers = {}
    num_attempts = 0

    sub = submissions[qs['submission_id']]
    snum = sub['user']['sis_user_id']
    sub_questions = quiz.submission_questions(qs)

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
                        for file in [canvas.file(a) for a
                                     in answer['attachment_ids']]:
                            raw_file_name = '%s_upload_%s' % \
                                            (common_substring,
                                             file['display_name'])
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
                        print('Missing rubric file for question %d (question group %s)' % (question_id, question['quiz_group_id']))

def flatten_list(l):
    if isinstance(l, list):
        for x in [x for x in l if isinstance(x, list)]:
            l.remove(x)
            l.extend(x)
    return l

def question_included(qid):
    if args.not_question and qid in args.not_question:
        return False
    elif args.only_question:
        return qid in args.only_question
    else:
        return True

parser = argparse.ArgumentParser()
canvas.Canvas.add_arguments(parser, quiz=True)
parser.add_argument("-p", "--output-prefix",
                    help="Path/prefix for output files")
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

canvas = canvas.Canvas(args=args)

zipfiles = {}

print('Reading data from Canvas...')
course = canvas.course(args.course, prompt_if_needed=True)
print('Using course: %s / %s' % (course['term']['name'],
                                 course['course_code']))

quiz = course.quiz(args.quiz, prompt_if_needed=True)
print('Using quiz: %s' % (quiz['title']))

if not args.output_prefix:
    args.output_prefix = re.sub(r'[^A-Za-z0-9-_]+', '', quiz['title'])
    print('Using prefix: %s' % args.output_prefix)

print('Retrieving quiz submissions...')
(quiz_submissions, submissions) = quiz.submissions()

print('\nGenerating files...')

if args.debug:
    with open('debug.json', 'w') as file:
        data = {}
        data['quiz'] = quiz.data
        data['quiz_submissions'] = quiz_submissions
        data['submissions'] = submissions
        json.dump(data, file, indent=2)

num_exams = 0
for qs in quiz_submissions:
    print("Exporting student %d out of %d..." %
          (num_exams + 1, len(quiz_submissions)), end='\r')
    process_submission(qs)
    num_exams += 1

for zip in zipfiles.values():
    zip.close()

print('\nDONE.')
