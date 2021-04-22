#! /usr/bin/python3

import os
import csv
import re
from os import path
import json
import zipfile
import argparse
import requests
import weasyprint

import canvas

def start_file(file_name):
    if path.exists(file_name):
        os.rename(file_name, file_name + '~')
    htmlfile = open(file_name, 'w')
    htmlfile.write('''<!DOCTYPE html>
    <html>
      <head></head>
      <body>
    ''')
    htmlfile_list.append(file_name)
    return htmlfile

def save_raw_answer(answer, identification):
    question = questions[answer['question_id']]
    if question['question_type'] == 'essay_question':
        raw_file_name = f'answer_{identification}.html'
        rawanswers_file.writestr(raw_file_name, answer['text'])
    elif question['question_type'] == 'file_upload_question':
        answer['text'] = '<div class="file-upload">See file(s): <ul>'
        for file in [canvas.file(a) for a in answer['attachment_ids']]:
            raw_file_name = f"answer_{identification}_{file['display_name']}"
            data = requests.get(file['url'])
            if data:
                rawanswers_file.writestr(raw_file_name, data.content)
                answer['text'] += f'<li>{raw_file_name}</li>'
        answer['text'] += '</ul></div>'


def write_exam_file(htmlfile, questions, qs=None):
    acct = ''
    snum = ''
    sname = ''
    answers = {}
    sub_questions = {}
    num_attempts = 0
    if qs != None:
        sub = submissions[qs['submission_id']]
        snum = sub['user']['sis_user_id']
        sname = sub['user']['name']
        if args.classlist:
            if snum in student_accounts:
                acct = student_accounts[snum]
            else:
                print(f'Account not found for student: {snum}')
        else:
            acct = snum

        sub_questions = quiz.submission_questions(qs)

        previous_score = -1
        previous_attempt = -1
        variation = {}
        for attempt in sub['submission_history']:
            if 'submission_data' in attempt:
                num_attempts += 1
                update_answer = False
                if attempt['score'] > previous_score:
                    previous_score = attempt['score']
                    previous_attempt = attempt['attempt']
                    update_answer = True
                elif attempt['score'] == previous_score and \
                     attempt['attempt'] > previous_attempt:
                    previous_attempt = attempt['attempt']
                    update_answer = True
                if attempt['attempt'] in variation.keys():
                    variation[attempt['attempt']] += 'x'
                else:
                    variation[attempt['attempt']] = ''
                for answer in attempt['submission_data']:
                    if question_included(answer['question_id']):
                        save_raw_answer(
                            answer,
                            f"{answer['question_id']}_{acct}_v{attempt['attempt']}{variation[attempt['attempt']]}")
                        if update_answer:
                            answers[answer['question_id']] = answer

    if args.classlist:
        htmlfile.write(f'''<div class='student-wrapper'>
        <span class='account-label'>Account:</span>
        <span><span class='account'>{acct}</span></span>
        </div>''')
    else:
        htmlfile.write(f'''<div class='student-wrapper'>
        <span class='snum-label'>Student Number:</span>
        <span><span class='snum'>{snum}</span></span>
        <span class='sname-label'>Name:</span>
        <span><span class='sname'>{sname}</span></span>
        </div>''')

    qn = 1
    for (question_id, question) in questions.items():
        question_name = question['question_name']
        question_text = question['question_text']
        question_type = question['question_type']
        if question_id in sub_questions and question_type == 'calculated_question':
            question_text = sub_questions[question_id]['question_text']
        if question_type == 'text_only_question':
            htmlfile.write(f'''
            <div class='text-only-question'>
             {question_text} 
            </div>
            ''')
            continue

        worth = question['points_possible']
        answer = None
        answer_text = ''
        points = ''

        if question_id in answers:
            answer = answers[question_id]
            answer_text = answer['text'] if 'text' in answer else ''
            points = answer['points']
        elif qs != None:
            question_type = None # To avoid formatting of multiple-choice
            answer_text = '''
            *** NO SUBMISSION ***<br/><br/>
            This typically means that this question is part of a question
            group, and the student did not receive this question in the
            group (i.e., the student answered a different question in
            this set).
            '''

        if question_type == 'calculated_question' or \
             question_type == 'short_answer_question' or \
             question_type == 'essay_question' or \
             question_type == 'numerical_question':
            pass # use answer exactly as provided
        elif question_type == 'true_false_question' or \
           question_type == 'multiple_choice_question' or \
           question_type == 'multiple_answers_question':
            answer_text = ''
            for pa in question['answers']:
                if question_type == 'multiple_answers_question':
                    key = f"answer_{pa['id']}"
                    choice = answer[key] if answer != None and key in answer else ''
                    if choice == '0': choice = ''
                else:
                    choice = 'X' if answer != None and 'answer_id' in answer and pa['id'] == answer['answer_id'] else ''
                answer_text += '<div class="mc-item">'
                answer_text += f'<span class="mc-item-space"><span>&nbsp;{choice}&nbsp;</span></span>'
                answer_text += f'&nbsp;&nbsp;'
                answer_text += f'<span class="mc-item-text">{pa["text"]}</span>'
                answer_text += '</div>'

        elif question_type == 'fill_in_multiple_blanks_question' or \
             question_type == 'multiple_dropdowns_question':
            answer_text = '<table class="multiple-blanks-table">'
            tokens = []
            dd_answers = {}
            for pa in question['answers']:
                if pa['blank_id'] not in tokens: tokens.append(pa['blank_id'])
                dd_answers[pa['id']] = pa['text']
            for token in tokens:
                key = f'answer_for_{token}'
                choice = answer[key] if answer != None and key in answer else ''
                if choice != '' and question_type == 'multiple_dropdowns_question' and choice in dd_answers:
                    choice = dd_answers[choice]
                answer_text += '<tr>'
                answer_text += f'<td class="multiple-blanks-token">{token}</td>'
                answer_text += '<td>=></td>'
                answer_text += f'<td class=multiple-blanks-answer>{choice}</td>'
                answer_text += '</tr>'
            answer_text += '</table>'

        elif question_type == 'matching_question':
            answer_text = '<table class="multiple-blanks-table">'
            matches = {}
            for match in question['matches']:
                matches[f"{match['match_id']}"] = match['text']
            for pa in question['answers']:
                key = f"answer_{pa['id']}"
                choice = matches[answer[key]] if answer != None and key in answer and answer[key] in matches else ''
                answer_text += '<tr>'
                answer_text += f'<td class="multiple-blanks-token">{pa["text"]}</td><td>=></td>'
                answer_text += '<td>=></td>'
                answer_text += f'<td class="multiple-blanks-answer">{choice}</td>'
                answer_text += '</tr>'
            answer_text += '</table>'

        elif question_type == 'file_upload_question':
            pass # This is handled in the processing of history above.
        elif question_type != None:
            raise ValueError(f'Invalid question type: "{question_type}"')

        num_attempts_text = '' if num_attempts <= 1 else f' ({num_attempts} attempts)'
        htmlfile.write(f'''<div class="question-preamble question-{question_id}"></div>
        <div class="question-container question-{question_id}">
        <h2 class="question-title">Question {question_id} [{question_name}]:</h2>
        <div class=question>{question_text}</div>
        <div class=points-container>
          <span class=points-possible><span>{worth}&nbsp;</span></span>
          <span class=points-canvas><span>{points}&nbsp;</span></span>
        </div>
        <h3 class=answer-title>Answer{num_attempts_text}:</h3>
        <div class=answer>{answer_text}</div>
        </div>
        ''')
        qn += 1

def end_file(htmlfile):
    htmlfile.write('</body>\n</html>')
    htmlfile.close()

def question_included(qid):
    if args.not_question and qid in args.not_question:
        return False
    elif args.only_question:
        return qid in args.only_question
    else:
        return True

parser = argparse.ArgumentParser()
canvas.Canvas.add_arguments(parser, quiz=True)
parser.add_argument("-l", "--classlist",
                    type=str, #type=argparse.FileType('r', newline=''),
                    help="CSV file containing student number and account. If used, account is provided on the front page, otherwise it will include name and student number.")
parser.add_argument("-p", "--output-prefix",
                    help="Path/prefix for output files")
group = parser.add_mutually_exclusive_group()
group.add_argument("--only-question", action='extend', nargs='+', type=int,
                   metavar="QUESTIONID", help="Questions to include")
group.add_argument("--not-question", action='extend', nargs='+', type=int,
                   metavar="QUESTIONID", help="Questions to exclude")
parser.add_argument("--css",
                    help="Additional CSS file to use in PDF creation.")
parser.add_argument("--template-only", action='store_true',
                    help="Create only the template, without students.")
args = parser.parse_args()

canvas = canvas.Canvas(args=args)

student_accounts = {}
htmlfile_list = []

if args.classlist:
    print('Reading classlist...')

    with open(args.classlist, 'r', newline='') as file:
        reader = csv.DictReader(file)
        if 'SNUM' not in reader.fieldnames:
            raise ValueError('Classlist CSV file does not contain student number.')
        if 'ACCT' not in reader.fieldnames:
            raise ValueError('Classlist CSV file does not contain account.')
        for row in reader:
            student_accounts[row['SNUM']] = row['ACCT']

print('Reading data from Canvas...')
course = canvas.course(args.course, prompt_if_needed=True)
print(f"Using course: {course['term']['name']} / {course['course_code']}")

quiz = course.quiz(args.quiz, prompt_if_needed=True)
print(f"Using quiz: {quiz['title']}")

if not args.output_prefix:
    args.output_prefix = re.sub(r'[^A-Za-z0-9-_]+', '', quiz['title'])
    print(f'Using prefix: {args.output_prefix}')

# Reading questions
print('Retrieving quiz questions...')
(questions, groups) = quiz.questions(question_included)

print('Retrieving quiz submissions...')
if args.template_only:
    quiz_submissions = []
    submissions = {}
else:
    (quiz_submissions, submissions) = quiz.submissions()

print('Generating HTML files...')

file_no = 1
template_file = start_file(f'{args.output_prefix}_template.html')
if not args.template_only:
    exams_file = start_file(f'{args.output_prefix}_exams_{file_no}.html')
    rawanswers_file = zipfile.ZipFile(f'{args.output_prefix}_raw_answers.zip', 'w')

write_exam_file(template_file, questions)

if args.debug:
    with open('debug.json', 'w') as file:
        data = {}
        data['quiz'] = quiz.data
        data['questions'] = questions
        data['quiz_submissions'] = quiz_submissions
        data['submissions'] = submissions
        json.dump(data, file, indent=2)

num_exams = 0
for qs in quiz_submissions:
    print(f"Exporting student {num_exams + 1} out of {len(quiz_submissions)}...", end='\r')
    write_exam_file(exams_file, questions, qs)
    num_exams += 1
    if num_exams % 20 == 0:
        end_file(exams_file)
        file_no += 1
        exams_file = start_file(f'{args.output_prefix}_exams_{file_no}.html')

end_file(template_file)
if not args.template_only:
    end_file(exams_file)
    rawanswers_file.close()

print('\nConverting to PDF...')
css = [weasyprint.CSS(path.join(path.dirname(__file__), 'canvasquiz.css'))]
if args.css:
    css.append(weasyprint.CSS(args.css))

for file in htmlfile_list:
    print(f'{file}...  ', end='\r')
    weasyprint.HTML(filename=file).write_pdf(f'{file}.pdf', stylesheets=css)

print('\nDONE. Created files:')
for file in htmlfile_list:
    print(f'- {file}.pdf')
if not args.template_only:
    print(f'- {args.output_prefix}_raw_answers.zip')
