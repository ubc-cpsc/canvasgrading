#! /usr/bin/python3

import os
import csv
import re
from os import path
import json
import requests
import weasyprint
import zipfile
import argparse

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
        raw_file_name = 'answer_%s.html' % identification
        rawanswers_file.writestr(raw_file_name, answer['text'])
    elif question['question_type'] == 'file_upload_question':
        answer['text'] = '<div class="file-upload">See file(s): <ul>'
        for file in [canvas.file(a) for a in answer['attachment_ids']]:
            raw_file_name = 'answer_%s_%s' % \
                            (identification, file['display_name'])
            data = requests.get(file['url'])
            if data:
                rawanswers_file.writestr(raw_file_name, data.content)
                answer['text'] += '<li>%s</li>' % raw_file_name
        answer['text'] += '</ul></div>'


def write_exam_file(htmlfile, questions, qs = None):
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
                print('Account not found for student: %s' % snum)
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
                        save_raw_answer(answer, '%d_%s_v%d%s' % \
                                        (answer['question_id'], acct,
                                         attempt['attempt'],
                                         variation[attempt['attempt']]))
                        if update_answer:
                            answers[answer['question_id']] = answer

    if args.classlist:
        htmlfile.write('''<div class='student-wrapper'>
        <span class='account-label'>Account:</span>
        <span><span class='account'>%s</span></span>
        </div>''' % acct)
    else:
        htmlfile.write('''<div class='student-wrapper'>
        <span class='snum-label'>Student Number:</span>
        <span><span class='snum'>%s</span></span>
        <span class='sname-label'>Name:</span>
        <span><span class='sname'>%s</span></span>
        </div>''' % (snum, sname))

    qn = 1
    for (question_id, question) in questions.items():
        question_name = question['question_name']
        question_text = question['question_text']
        question_type = question['question_type']
        if question_id in sub_questions and question_type == 'calculated_question':
            question_text = sub_questions[question_id]['question_text']
        if question_type == 'text_only_question':
            htmlfile.write('''
            <div class='text-only-question'>
              %s
            </div>
            ''' % question_text)
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
                    key = 'answer_%s' % pa['id']
                    choice = answer[key] if answer != None and key in answer else ''
                    if choice == '0': choice = ''
                else:
                    choice = 'X' if answer != None and 'answer_id' in answer and pa['id'] == answer['answer_id'] else ''
                answer_text += '<div class="mc-item"><span class="mc-item-space"><span>&nbsp;%s&nbsp;</span></span>&nbsp;&nbsp;<span class="mc-item-text">%s</span></div>' % (choice, pa['text'])
            
        elif question_type == 'fill_in_multiple_blanks_question' or \
             question_type == 'multiple_dropdowns_question':
            answer_text = '<table class="multiple-blanks-table">'
            tokens = []
            dd_answers = {}
            for pa in question['answers']:
                if pa['blank_id'] not in tokens: tokens.append(pa['blank_id'])
                dd_answers[pa['id']] = pa['text']
            for token in tokens:
                key = 'answer_for_%s' % token
                choice = answer[key] if answer != None and key in answer else ''
                if choice != '' and question_type == 'multiple_dropdowns_question' and choice in dd_answers:
                    choice = dd_answers[choice]
                answer_text += '<tr><td class="multiple-blanks-token">%s</td><td>=></td><td class=multiple-blanks-answer>%s</td></tr>' % (token, choice)
            answer_text += '</table>'
                
        elif question_type == 'matching_question':
            answer_text = '<table class="multiple-blanks-table">'
            matches = {}
            for match in question['matches']:
                matches['%d' % match['match_id']] = match['text']
            for pa in question['answers']:
                key = 'answer_%s' % pa['id']
                choice = matches[answer[key]] if answer != None and key in answer and answer[key] in matches else ''
                answer_text += '<tr><td class="multiple-blanks-token">%s</td><td>=></td><td class="multiple-blanks-answer">%s</td></tr>' % (pa['text'], choice)
            answer_text += '</table>'
        
        elif question_type == 'file_upload_question':
            pass # This is handled in the processing of history above.
        elif question_type != None:
            raise ValueError('Invalid question type: "%s"' % question_type)
        
        htmlfile.write('''<div class="question-preamble question-%d"></div>
        <div class="question-container question-%d">
        <h2 class="question-title">Question %d [%s]:</h2>
        <div class=question>%s</div>
        <div class=points-container>
          <span class=points-possible><span>%s&nbsp;</span></span>
          <span class=points-canvas><span>%s&nbsp;</span></span>
        </div>
        <h3 class=answer-title>Answer%s:</h3>
        <div class=answer>%s</div>
        </div>
        ''' % (question_id, question_id, question_id, question_name,
               question_text, worth, points,
               '' if num_attempts <= 1 else ' (%d attempts)' % num_attempts,
               answer_text))
        qn += 1

def flatten_list(l):
    if isinstance(l, list):
        for x in [x for x in l if isinstance(x, list)]:
            l.remove(x)
            l.extend(x)
    return l
    
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
group.add_argument("--only-question", action='append', nargs='+', type=int,
                   metavar="QUESTIONID", help="Questions to include")
group.add_argument("--not-question", action='append', nargs='+', type=int,
                   metavar="QUESTIONID", help="Questions to exclude")
parser.add_argument("--css",
                    help="Additional CSS file to use in PDF creation.")
parser.add_argument("--template-only", action='store_true',
                    help="Create only the template, without students.")
parser.add_argument("-d", "--debug", help="Enable debugging mode",
                    action='store_true')
args = parser.parse_args()

flatten_list(args.only_question)
flatten_list(args.not_question)

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
print('Using course: %s / %s' % (course['term']['name'],
                                 course['course_code']))

quiz = course.quiz(args.quiz, prompt_if_needed=True)
print('Using quiz: %s' % (quiz['title']))

if not args.output_prefix:
    args.output_prefix = re.sub(r'[^A-Za-z0-9-_]+', '', quiz['title'])
    print('Using prefix: %s' % args.output_prefix);

# Reading questions
print('Retrieving quiz questions...')
(questions, groups) = quiz.questions(question_included)

print('Retrieving quiz submissions...')
if args.template_only:
    quiz_submissions = []
    submissions = {}
else:
    (quiz_submissions, submissions) = quiz.submissions(debug=args.debug)

print('Generating HTML files...')

file_no = 1;
template_file = start_file(args.output_prefix + '_template.html')
if not args.template_only:
    exams_file    = start_file(args.output_prefix + '_exams_%d.html' % file_no)
    rawanswers_file = zipfile.ZipFile(args.output_prefix + '_raw_answers.zip', 'w')

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
    print("Exporting student %d out of %d..." %
          (num_exams + 1, len(quiz_submissions)), end='\r');
    write_exam_file(exams_file, questions, qs)
    num_exams += 1
    if num_exams % 20 == 0:
        end_file(exams_file)
        file_no += 1
        exams_file = start_file(args.output_prefix + '_exams_%d.html' % file_no)

end_file(template_file)
if not args.template_only:
    end_file(exams_file)
    rawanswers_file.close()

print('\nConverting to PDF...')
css = [weasyprint.CSS(path.join(path.dirname(__file__),'canvasquiz.css'))]
if args.css:
    css.append(weasyprint.CSS(args.css))

for file in htmlfile_list:
    print(file + '...  ', end='\r');
    weasyprint.HTML(filename=file).write_pdf(file + '.pdf', stylesheets=css)

print('\nDONE. Created files:')
for file in htmlfile_list:
    print('- ' + file + '.pdf')
if not args.template_only:
    print('- ' + args.output_prefix + '_raw_answers.zip')
