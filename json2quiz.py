#! /usr/bin/python3

import os
from os import path
import json
import argparse
from collections import OrderedDict

import canvas

QUIZ_REQ_FIELDS = ['id', 'title', 'description', 'quiz_type',
                   'assignment_group_id', 'time_limit', 'shuffle_answers',
                   'hide_results', 'show_correct_answers',
                   'show_correct_answers_at', 'hide_correct_answers_at',
                   'show_correct_answers_last_attempt', 'allowed_attempts',
                   'scoring_policy', 'one_question_at_a_time', 'cant_go_back',
                   'access_code', 'ip_filter', 'due_at', 'lock_at', 'unlock_at',
                   'published', 'one_time_results',
                   'only_visible_to_overrides']
GROUP_REQ_FIELDS = ['id', 'name', 'pick_count', 'question_points',
                    'assessment_question_bank_id', 'position']
QUESTION_REQ_FIELDS = ['id', 'question_name', 'question_text', 'quiz_group_id',
                       'question_type', 'position', 'points_possible',
                       'correct_comments', 'incorrect_comments',
                       'neutral_comments', 'text_after_answers', 'answers']

def canvas_to_alternate(question):
    if question['question_type'] == 'fill_in_multiple_blanks_question':
        question['options'] = options = OrderedDict()
        for answer in question['answers']:
            if answer['blank_id'] not in options:
                options[answer['blank_id']] = answer['text']
            elif isinstance(options[answer['blank_id']], list):
                options[answer['blank_id']] += answer['text']
            else:
                options[answer['blank_id']] = [options[answer['blank_id']],
                                               answer['text']]
        del question['answers']
    return question

def alternate_to_canvas(question):
    if 'options' not in question: return question
    if question['question_type'] == 'fill_in_multiple_blanks_question':
        question['answers'] = []
        for token, tokenv in question['options'].items():
            for value in tokenv if isinstance(tokenv, list) else [tokenv]:
                question['answers'].append(
                    {'text': value, 'weigth': 100.0, 'blank_id': token})
    return question

parser = argparse.ArgumentParser()
canvas.Canvas.add_arguments(parser, quiz=True)
parser.add_argument("json_file",
                    help="JSON file, may be an input file (for pushing), an oautput file (for loading), or both (for sync).")
parser.add_argument("-p", "--push-quiz", action='store_true',
                    help="Push JSON values to Canvas")
parser.add_argument("-l", "--load-quiz", action='store_true',
                    help="Load JSON from values retrieved from Canvas")
parser.add_argument("-s", "--strip", action='store_true',
                    help="Strip from output JSON values that cannot be pushed back in updates.")
parser.add_argument("-a", "--alternative-format", action='store_true',
                    help="Use alternative format for answers in some types of questions.")
args = parser.parse_args()
canvas = canvas.Canvas(args=args)

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
    values_from_json = json.load(json_file, object_pairs_hook=OrderedDict)
    if not args.quiz and 'quiz' in values_from_json and \
       'id' in values_from_json['quiz']:
        args.quiz = values_from_json['quiz']['id']
else:
    values_from_json = {}

print('Reading data from Canvas...')
course = canvas.course(args.course, prompt_if_needed=True)
print('Using course: %s / %s' % (course['term']['name'],
                                 course['course_code']))

quiz = course.quiz(args.quiz, prompt_if_needed=True)
print('Using quiz: %s' % (quiz['title']))

# Reading questions
print('Retrieving current quiz questions...')
(questions, groups) = quiz.questions()

if 'quiz' in values_from_json:
    print('Pushing updates to quiz...')
    quiz = quiz.update_quiz(values_from_json['quiz'])

groups_from_file = {}
if 'groups' in values_from_json:
    print('Pushing updates to question groups...')
    for (group_id, group) in values_from_json['groups'].items():
        existing_id = None
        try:
            if int(group_id) in groups: existing_id = int(group_id)
        except:
            pass
        group = quiz.update_question_group(existing_id, group)['quiz_groups'][0]
        groups_from_file[group_id] = group
        groups[group['id']] = group

questions_from_file = {}
if 'questions' in values_from_json:
    print('Pushing updates to questions...')
    for (question_id, question) in values_from_json['questions'].items():
        if question['quiz_group_id'] in groups_from_file:
            question['quiz_group_id'] = groups_from_file[question['quiz_group_id']]['id']
        existing_id = None
        try:
            if int(question_id) in questions: existing_id = int(question_id)
        except:
            pass
        question = quiz.update_question(existing_id,
                                        alternate_to_canvas(question))
        question['updated'] = True
        questions_from_file[question_id] = question
        questions[question['id']] = question
    for (question_id, question) in questions.items():
        if 'updated' not in question:
            print('Question %d (%s) not found in JSON file. Text:\n%s' %
                  (question_id, question['question_name'],
                   question['question_text']))
            delete = ''
            while delete not in ['y', 'n']:
                delete = input('Delete [y/n]? ').lower()
            if delete == 'y':
                quiz.delete_question(question_id)

if 'order' in values_from_json:
    print('Pushing updates to question order...')
    for item in values_from_json['order']:
        if item['type'] == 'question':
            if item['id'] in questions_from_file:
                item['id'] = questions_from_file[item['id']]['id']
        elif item['type'] == 'group':
            if item['id'] in groups_from_file:
                item['id'] = groups_from_file[item['id']]['id']
    quiz.reorder_questions(values_from_json['order'])

if len(values_from_json) > 0:
    # Reading questions
    print('Retrieving updated list of quiz questions...')
    (questions, groups) = quiz.questions()

if args.strip:
    quiz      = {k:v for k, v in quiz.items()
                 if k in QUIZ_REQ_FIELDS}
    groups    = {id:{k:v for k, v in group.items()
                     if k in GROUP_REQ_FIELDS}
                 for id, group in groups.items()}
    questions = {id:{k:v for k, v in question.items()
                     if k in QUESTION_REQ_FIELDS}
                 for id, question in questions.items()}

if args.alternative_format:
    for question in questions.values():
        canvas_to_alternate(question)

order = []
groups_ordered = set()
for question in questions.values():
    if question['quiz_group_id']:
        if question['quiz_group_id'] not in groups_ordered:
            order.append({'type': 'group',
                          'id': question['quiz_group_id'],
                          'name': groups[question['quiz_group_id']]['name'],
                          'points': groups[question['quiz_group_id']]['question_points']})
            groups_ordered.add(question['quiz_group_id'])
    else:
        order.append({'type': 'question',
                      'id': question['id'],
                      'name': question['question_name'],
                      'points': question['points_possible']})

if args.load_quiz:
    print('Saving values back to JSON file...')
    json_file.seek(0)
    json.dump({'quiz': {k: v for k, v in quiz.items()},
               'order': order,
               'groups': groups,
               'questions': questions
              }, json_file, indent=2)
    json_file.truncate()

json_file.close()
print('\nDONE.')
