#! /usr/bin/python3

import sys
import csv
import re
import json
import zipfile
import argparse

import canvas

parser = argparse.ArgumentParser()
parser.add_argument("grades", type=str,
                    help="CSV file containing grades")
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("-f", "--canvas-token-file", type=argparse.FileType('r'),
                   help="File containing the Canvas token used for authentication")
group.add_argument("-t", "--canvas-token",
                   help="Canvas token used for authentication")
parser.add_argument("-c", "--course", type=int, help="Course ID")
parser.add_argument("-q", "--quiz", type=int, help="Quiz ID")
args = parser.parse_args()

if args.canvas_token_file:
    args.canvas_token = args.canvas_token_file.read().strip()
    args.canvas_token_file.close()
canvas = canvas.Canvas(args.canvas_token)

grades = []
student_sub = {}

print('Loading grades...')

with open(args.grades, newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    if not all(x in reader.fieldnames for x in \
               ['Question','Student','Attempt','Grade','Comments']):
        raise ValueError('Classlist CSV file must contain at least the following columns: Question,Student,Attempt,Grade,Comments')
    for row in reader:
        grades.append(row)

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

print('Retrieving quiz submissions...')
(quiz_submissions, submissions) = canvas.submissions(course, quiz,
                                                     include_history=False)

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
          (num_exams + 1, len(grades)), end='\r');

    for sub in student_sub[grade['Student']]:
        for qs in sub['quiz_submissions']:
            if str(qs['attempt']) == grade['Attempt']:
                canvas.send_quiz_grade(course, qs,
                                       int(grade['Question']),
                                       grade['Grade'],
                                       grade['Comments'])
    
    num_exams += 1

print('\nDONE.')
