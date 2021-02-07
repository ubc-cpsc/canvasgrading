#! /usr/bin/python3

import os
import re
from os import path
import json
import argparse
from collections import OrderedDict
import uuid

import canvas

def file_name_only(name):
    return re.sub('[\W_]+', '', name)

parser = argparse.ArgumentParser()
canvas.Canvas.add_arguments(parser, quiz=True)
parser.add_argument("pl_repo",
                    help="Directory where PrairieLearn repo is stored")
parser.add_argument("pl_course_instance",
                    help="Course instance where assessment will be created")
parser.add_argument("-s", "--assessment-set", default="Quiz",
                    help="Assessment set to assign this assessment to")
parser.add_argument("-n", "--assessment-number", default="",
                    help="Assessment set to assign this assessment to")
parser.add_argument("--topic", default="None",
                    help="Assessment set to assign this assessment to")
parser.add_argument("-d", "--debug", help="Enable debugging mode",
                    action='store_true')
args = parser.parse_args()
canvas = canvas.Canvas(args=args)

if not os.path.exists(os.path.join(args.pl_repo, 'infoCourse.json')):
    raise Exception("Provided directory is not a PrairieLearn repository")

questions_dir = os.path.join(args.pl_repo, 'questions')
if not os.path.isdir(questions_dir):
    os.makedirs(questions_dir)
assessments_dir = os.path.join(args.pl_repo, 'courseInstances', args.pl_course_instance, 'assessments')
if not os.path.isdir(assessments_dir):
    os.makedirs(assessments_dir)

print('Reading data from Canvas...')
course = canvas.course(args.course, prompt_if_needed=True)
print('Using course: %s / %s' % (course['term']['name'],
                                 course['course_code']))

quiz = course.quiz(args.quiz, prompt_if_needed=True)
print('Using quiz: %s' % (quiz['title']))

# Reading questions
print('Retrieving quiz questions from Canvas...')
(questions, groups) = quiz.questions()

quiz_name = os.path.join(assessments_dir, file_name_only(quiz['title']))
if os.path.exists(quiz_name):
    suffix = 1
    while os.path.exists(f'{quiz_name}_{suffix}'):
        suffix += 1
    quiz_name = f'{quiz_name}_{suffix}'
os.makedirs(quiz_name)

pl_quiz = {
    'uuid': str(uuid.uuid4()),
    'type': 'Exam' if quiz['time_limit'] else 'Homework',
    'title': quiz['title'],
    'text': quiz['description'],
    'set': args.assessment_set,
    'number': args.assessment_number,
    'allowAccess': [{
        'startDate': quiz['unlock_at'],
        'endDate': quiz['lock_at'],
        'credit': 100,
        'timeLimitMin': quiz['time_limit'],
        'showClosedAssessment': True,
        'showClosedAssessmentScore': True
    }],
    'zones': [{
        'questions': []
    }],
    'comment': f'Imported from Canvas, quiz {quiz["id"]}'
}

if (quiz['access_code']):
    quiz['allowAccess'][0]['password'] = quiz['access_code']
    quiz['allowAccess'][1]['password'] = quiz['access_code']

for question in questions.values():
    print(f'Handling question {question["id"]}...')
    print(question['question_text'])
    question_title = input('Question title: ')
    question_name = file_name_only(question_title)
    suffix = 0
    while os.path.exists(os.path.join(questions_dir, question_name)):
        suffix += 1
        question_name = f'{file_name_only(question_title)}_{suffix}'
    question_dir = os.path.join(questions_dir, question_name)
    os.makedirs(question_dir)

    pl_quiz['zones'][0]['questions'].append({
        'id': question_name,
        'points': question['points_possible']
    })
    
    with open(os.path.join(question_dir, 'info.json'), 'w') as info:
        json.dump({
            'uuid': str(uuid.uuid4()),
            'type': 'v3',
            'title': question_title,
            'topic': args.topic,
            'tags': ['fromcanvas']
        }, info, indent=4)

    with open(os.path.join(question_dir, 'question.html'), 'w') as template:
        if question['question_type'] == 'multiple_answers_question':
            template.write('<pl-question-panel>\n<p>\n')
            template.write(question['question_text'] + '\n')
            template.write('</p>\n</pl-question-panel>\n')
            template.write('<pl-checkbox answers-name="checkbox">\n')
            for answer in question['answers']:
                if answer['weight']:
                    template.write('  <pl-answer correct="true">')
                else:
                    template.write('  <pl-answer>')
                template.write(answer['text'] + '</pl-answer>\n')
            template.write('</pl-checkbox>\n')
        elif question['question_type'] == 'true_false_question' or question['question_type'] == 'multiple_choice_question':
            template.write('<pl-question-panel>\n<p>\n')
            template.write(question['question_text'] + '\n')
            template.write('</p>\n</pl-question-panel>\n')
            template.write('<pl-multiple-choice answers-name="mc">\n')
            for answer in question['answers']:
                if answer['weight']:
                    template.write('  <pl-answer correct="true">')
                else:
                    template.write('  <pl-answer>')
                template.write(answer['text'] + '</pl-answer>\n')
            template.write('</pl-checkbox>\n')
        elif question['question_type'] == 'numerical_question':
            template.write('<pl-question-panel>\n<p>\n')
            template.write(question['question_text'] + '\n')
            template.write('</p>\n</pl-question-panel>\n')
            answer = question['answers'][0]
            if answer['numerical_answer_type'] == 'exact_answer' and abs(answer['exact'] - int(answer['exact'])) < 0.001 and answer['margin'] == 0:
                template.write(f'<pl-integer-input answers-name="value" correct-answer="{int(answer["exact"])}"></pl-integer-input>\n')
            elif answer['numerical_answer_type'] == 'exact_answer':
                template.write(f'<pl-number-input answers-name="value" correct-answer="{answer["exact"]}" atol="{answer["margin"]}"></pl-number-input>\n')
            elif answer['numerical_answer_type'] == 'range_answer':
                average = (answer["end"] + answer["start"]) / 2
                margin = abs(answer["end"] - average)
                template.write(f'<pl-number-input answers-name="value" correct-answer="{average}" atol="{margin}"></pl-number-input>\n')
            elif answer['numerical_answer_type'] == 'precision_answer':
                template.write(f'<pl-number-input answers-name="value" correct-answer="{answer["approximate"]}" comparison="sigfig" digits="{answer["precision"]}"></pl-number-input>\n')
            else:
                print(f'Invalid numerical answer type: {answer["numerical_answer_type"]}')
                template.write(f'<pl-number-input answers-name="value"></pl-integer-input>\n')
        elif question['question_type'] == 'short_answer_question':
            template.write('<pl-question-panel>\n<p>\n')
            template.write(question['question_text'] + '\n')
            template.write('</p>\n</pl-question-panel>\n')
            answer = question['answers'][0]
            template.write(f'<pl-string-input answers-name="input" correct-answer="{answer["text"]}"></pl-string-inpust>\n')
            
        elif question['question_type'] == 'fill_in_multiple_blanks_question':
            question_text = question['question_text']
            options = {}
            for answer in question['answers']:
                if answer['blank_id'] not in options:
                    options[answer['blank_id']] = []
                options[answer['blank_id']].append(answer)
            for answer_id, answers in options.items():
                question_text.replace(f'[{answer_id}]', f'<pl-string-input answers-name="{answer_id}" correct-answer="{answers[0]["text"]}" remove-spaces="true" ignore-case="true" display="inline"></pl-string-input>')
                
            template.write(question_text + '\n')
            
        elif question['question_type'] == 'matching_question':
            template.write('<pl-question-panel>\n<p>\n')
            template.write(question['question_text'] + '\n')
            template.write('</p>\n</pl-question-panel>\n')
            template.write('<markdown>\n|   |   |\n|---|---|\n')
            for answer in question['answers']:
                template.write(f'| {answer["text"]} | <pl-dropdown answers-name="answer{answer["id"]}">')
                for match in question['matches']:
                    template.write(f'<pl-answer')
                    if match['match_id'] == answer['match_id']:
                        template.write(f' correct="true"')
                    template.write(f'>{match["text"]}</pl-answer>')
                template.write('</pl-dropdown> |\n')
            template.write('</markdown>\n')
            
        else:
            print('Unsupported question type: ' + question['question_type'])

        if question['correct_comments'] or question['neutral_comments']:
            template.write('<pl-answer-panel>\n<p>\n')
            if question.get('correct_comments_html', False):
                template.write(question['correct_comments_html'] + '\n')
            elif question['correct_comments']:
                template.write(question['correct_comments'] + '\n')
            if question.get('neutral_comments_html', False):
                template.write(question['neutral_comments_html'] + '\n')
            elif question['neutral_comments']:
                template.write(question['neutral_comments'] + '\n')
            template.write('</p>\n</pl-answer-panel>\n')

with open(os.path.join(quiz_name, 'infoAssessment.json'), 'w') as assessment:
    json.dump(pl_quiz, assessment, indent=4)

print('\nDONE.')
