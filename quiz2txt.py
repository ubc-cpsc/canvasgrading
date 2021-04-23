#! /usr/bin/python3

import os
import re
import json
import zipfile
import argparse
import requests
import canvas

def process_submission(qsub):
    num_attempts = 0

    sub = submissions[qsub['submission_id']]
    snum = sub['user']['sis_user_id']
    sub_questions = quiz.submission_questions(qsub)

    variation = {}
    for attempt in sub['submission_history']:
        if 'submission_data' not in attempt:
            continue

        num_attempts += 1
        if attempt['attempt'] in variation.keys():
            variation[attempt['attempt']] += 'x'
        else:
            variation[attempt['attempt']] = ''

        for answer in attempt['submission_data']:
            question_id = answer['question_id']
            if not question_included(question_id):
                continue

            if question_id not in sub_questions:
                print(f"Question {question_id} does not have associated text.")
                continue

            question = sub_questions[question_id]
            if question['question_type'] not in ['essay_question', 'file_upload_question']:
                continue

            if question_id not in zipfiles:
                zipfiles[question_id] = zipfile.ZipFile(
                    f"{args.output_prefix}_{question['question_name']}_{question_id}.zip", 'w')
            zipf = zipfiles[question_id]
            common_substring = f"{question_id}_{snum}_v{attempt['attempt']}{variation[attempt['attempt']]}"
            # if question['quiz_group_id'] != None:
            #     common_substring = 'qg%d_%s' % (question['quiz_group_id'], common_substring)
            if question['question_type'] == 'essay_question':
                raw_file_name = f'{common_substring}_answer.html'
                zipf.writestr(raw_file_name, f"/* {question['question_text']} */\n{answer['text']}")
            elif question['question_type'] == 'file_upload_question':
                for cfile in [canvas.file(a) for a in answer['attachment_ids']]:
                    raw_file_name = f"{common_substring}_upload_{cfile['display_name']}"
                    data = requests.get(cfile['url'])
                    if data:
                        zipf.writestr(raw_file_name, data.content)
            rubric_file = f'{common_substring}_rubric.txt'
            template_file = f'{args.output_prefix}_rubtempl_q{question_id}.txt'
            if not os.path.isfile(template_file) and question['quiz_group_id'] is not None:
                template_file = f"{args.output_prefix}_rubtempl_qg{question['quiz_group_id']}.txt"
            if os.path.isfile(template_file):
                zipf.write(template_file, arcname=rubric_file)
            else:
                print(f"Missing rubric file for question {question_id} (question group {question['quiz_group_id']})")

def question_included(qid):
    if args.not_question and qid in args.not_question:
        return False
    if args.only_question:
        return qid in args.only_question
    return True

parser = argparse.ArgumentParser()
canvas.Canvas.add_arguments(parser, quiz=True)
parser.add_argument("-p", "--output-prefix",
                    help="Path/prefix for output files")
group = parser.add_mutually_exclusive_group()
group.add_argument("--only-question", action='extend', nargs='+', type=int, metavar="QUESTIONID",
                   help="Questions to include")
group.add_argument("--not-question", action='extend', nargs='+', type=int, metavar="QUESTIONID",
                   help="Questions to exclude")
args = parser.parse_args()

canvas = canvas.Canvas(args=args)

zipfiles = {}

print('Reading data from Canvas...')
course = canvas.course(args.course, prompt_if_needed=True)
print(f"Using course: {course['term']['name']} / {course['course_code']}")

quiz = course.quiz(args.quiz, prompt_if_needed=True)
print(f"Using quiz: {quiz['title']}")

if not args.output_prefix:
    args.output_prefix = re.sub(r'[^A-Za-z0-9-_]+', '', quiz['title'])
    print(f'Using prefix: {args.output_prefix}')

print('Retrieving quiz submissions...')
(quiz_submissions, submissions) = quiz.submissions()

print('\nGenerating files...')

if args.debug:
    with open('debug.json', 'w') as file:
        ddata = {}
        ddata['quiz'] = quiz.data
        ddata['quiz_submissions'] = quiz_submissions
        ddata['submissions'] = submissions
        json.dump(ddata, file, indent=2)

num_exams = 0
for quizsub in quiz_submissions:
    print(f"Exporting student {num_exams + 1} out of {len(quiz_submissions)}...", end='\r')
    process_submission(quizsub)
    num_exams += 1

for zf in zipfiles.values():
    zf.close()

print('\nDONE.')
