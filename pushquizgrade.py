#! /usr/bin/python3

import sys
import csv
import re
import json
import zipfile
import argparse

import canvas

parser = argparse.ArgumentParser()
canvas.Canvas.add_arguments(parser, quiz=True)
parser.add_argument("grades", type=str,
                    help="CSV file containing grades")
args = parser.parse_args()

canvas = canvas.Canvas(args=args)

grades = []
student_sub = {}

print('Loading grades...')

with open(args.grades, newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    if not all(x in reader.fieldnames for x in \
               ['Question', 'Student', 'Attempt', 'Grade', 'Comments']):
        raise ValueError('Classlist CSV file must contain at least the following columns: Question,Student,Attempt,Grade,Comments')
    for row in reader:
        grades.append(row)

print('Reading data from Canvas...')
course = canvas.course(args.course, prompt_if_needed=True)
print('Using course: %s / %s' % (course['term']['name'],
                                 course['course_code']))

quiz = course.quiz(args.quiz, prompt_if_needed=True)
print('Using quiz: %s' % (quiz['title']))

print('Retrieving quiz submissions...')
(quiz_submissions, submissions) = quiz.submissions(include_history=False)

for submission in submissions.values():
    submission['quiz_submissions'] = []
    snum = submission['user']['sis_user_id']
    if snum not in student_sub:
        student_sub[snum] = []
    student_sub[snum].append(submission)
for qs in quiz_submissions:
    sub = submissions[qs['submission_id']]
    sub['quiz_submissions'].append(qs)

print('\nSending grades...')

num_exams = 0
for grade in grades:
    print("Updating grade %d out of %d..." %
          (num_exams + 1, len(grades)), end='\r')

    for sub in student_sub[grade['Student']]:
        for qs in sub['quiz_submissions']:
            if str(qs['attempt']) == grade['Attempt']:
                quiz.send_quiz_grade(qs, int(grade['Question']),
                                     grade['Grade'], grade['Comments'])

    num_exams += 1

print('\nDONE.')
