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

def write_exam_file(htmlfile, questions, qs = None):
    acct = ''
    answers = {}
    sub_questions = {}
    num_attempts = 0
    if qs != None:
        sub = submissions[qs['submission_id']]
        snum = sub['user']['sis_user_id']
        if snum in student_accounts:
            acct = student_accounts[snum]
        else:
            print('Account not found for student: %s' % snum)
        # Get question listed to student
        for r in api_request('/quiz_submissions/%d/questions' % qs['id']):
            for q in r['quiz_submission_questions']:
                sub_questions[q['id']] = q

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
                elif attempt['score'] == previous_score and attempt['attempt'] > previous_attempt:
                    previous_attempt = attempt['attempt']
                    update_answer = True
                if attempt['attempt'] in variation.keys():
                    variation[attempt['attempt']] += 'x'
                else:
                    variation[attempt['attempt']] = ''
                for answer in attempt['submission_data']:
                    question_id = answer['question_id']
                    if question_included(question_id):
                        question = questions[question_id]
                        if question['question_type'] == 'essay_question':
                            raw_file_name = 'answer_%d_%s_v%d%s.html' % \
                                            (answer['question_id'], acct, attempt['attempt'], variation[attempt['attempt']])
                            rawanswers_file.writestr(raw_file_name, answer['text'])
                        elif question['question_type'] == 'file_upload_question':
                            answer['text'] = 'See file(s): <ul>'
                            for attach in answer['attachment_ids']:
                                for file in api_request('/files/%s' % attach):
                                    raw_file_name = 'answer_%d_%s_v%d%s_%s' % \
                                                    (answer['question_id'], acct, attempt['attempt'], variation[attempt['attempt']], file['display_name'])
                                    data = requests.get(file['url'])
                                    if data:
                                        rawanswers_file.writestr(raw_file_name, data.content)
                                        answer['text'] += '<li>%s</li>' % raw_file_name

                    if update_answer:
                        answers[answer['question_id']] = answer

    htmlfile.write('''<div style="text-align: center; margin: auto; font-size: xx-large;
                                  page-break-after: always; height: 20cm; vertical-align: middle;">
    CS Alias:<br/>
    <span style="display: inline-block;">
    <div style="display: table-cell; vertical-align: middle;
                height: 3cm; width: 10cm; background: #7f7;
                font-family: cursive; margin: auto;">%s</div></span>
    </div>''' % acct)
    qn = 1
    wrap = textwrap.TextWrapper(width=100, replace_whitespace=False)
    for question_id in sorted(questions.keys()):
        question = questions[question_id]
        question_name = question['question_name']
        question_text = question['question_text']
        question_type = question['question_type']
        if question_id in sub_questions and question_type == 'calculated_question':
            question_text = sub_questions[question_id]['question_text']
        if question_type == 'text_only_question':
            htmlfile.write('''
            <div class=text_only_question
                 style="page-break-after: always;">\n%s
            </div>
            ''' % wrap.fill(question_text))
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
                answer_text += '(<span style="width: 1cm; height: 1cm; border: 2px black; ' + \
                    'display: inline-block; text-align: center;">&nbsp;%s&nbsp;</span>)&nbsp;&nbsp;%s<br />' % (choice, pa['text'])
            
        elif question_type == 'fill_in_multiple_blanks_question' or \
             question_type == 'multiple_dropdowns_question':
            answer_text = '<table>'
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
                answer_text += '<tr><td style="text-align: right;">%s</td><td>=></td><td>%s</td></tr>' % (token, choice)
            answer_text += '</table>'
                
        elif question_type == 'matching_question':
            answer_text = '<table>'
            matches = {}
            for match in question['matches']:
                matches['%d' % match['match_id']] = match['text']
            for pa in question['answers']:
                key = 'answer_%s' % pa['id']
                choice = matches[answer[key]] if answer != None and key in answer and answer[key] in matches else ''
                answer_text += '<tr><td style="text-align: right;">%s</td><td>=></td><td>%s</td></tr>' % (pa['text'], choice)
            answer_text += '</table>'
        
        elif question_type == 'file_upload_question':
            pass # This is handled in the processing of history above.
        elif question_type != None:
            raise ValueError('Invalid question type: "%s"' % question_type)
                        
        htmlfile.write('''<div style="page-break-after: always;"></div>
        <div class=question_container style="page-break-inside: avoid; position: absolute;">
        <h2>Question %d [%s]:</h2>
        <div class=question style='font-size: x-small; max-height: 5cm; overflow: hidden; background: #ccc;'>
          %s
        </div>
        <table>
          <tr><td>Points possible:</td>
            <td><div style="display: table-cell; width: 2cm; vertical-align: middle;
                 height: 1cm; background: cyan; text-align: center;">%s&nbsp;</div></td>
            <td>Canvas autograder points:</td>
            <td><div style="display: table-cell; width: 2cm; vertical-align: middle;
                 height: 1cm; background: yellow; text-align: center;">%s&nbsp;</div></td></tr>
        </table>
        <h3>Answer%s:</h3>
        <div class=answer style='font-size: x-small; background: #eee;'>
          %s
        </div>
        </div>
        ''' % (question_id, question_name, question_text, worth, points,
               '' if num_attempts <= 1 else ' (%d attempts)' % num_attempts,
               answer_text))
        qn += 1
        
    
def end_file(htmlfile):
    htmlfile.write('</body>\n</html>')
    htmlfile.close()

def api_request(request, stopAtFirst = False):
    retval = []
    response = requests.get(MAIN_URL + request, headers = token_header)
    while True:
        retval.append(response.json())
        if stopAtFirst or 'current' not in response.links or \
           'last' not in response.links or \
           response.links['current']['url'] == response.links['last']['url']:
            break
        response = requests.get(response.links['next']['url'],
                                headers = token_header)
    return retval

def question_included(qid):
    return len(sys.argv) <= 6 or str(qid) in sys.argv[6]
    
exam_name       = sys.argv[1]
classlist_csv   = sys.argv[2]
token_file_name = sys.argv[3] 

courses = []
quizzes = []
students = {}
student_accounts = {}
submissions = {}
quiz_submissions = []
questions = {}
htmlfile_list = []

print('Reading classlist...')

with open(classlist_csv, newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    if 'SNUM' not in reader.fieldnames:
        raise ValueError('Classlist CSV file does not contain student number.')
    if 'ACCT' not in reader.fieldnames:
        raise ValueError('Classlist CSV file does not contain account.')
    for row in reader:
        student_accounts[row['SNUM']] = row['ACCT']

print('Reading data from Canvas...')

with open(token_file_name) as token_file:
    token = token_file.read().strip()
    token_header = {'Authorization': 'Bearer %s' % token}

# Reading course list
for list in api_request('/courses?include[]=term&state[]=available'):
    courses += list

course = None
if len(sys.argv) > 4:
    for lcourse in courses:
        if str(lcourse['id']) == sys.argv[4]:
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
if len(sys.argv) > 5:
    for lquiz in quizzes:
        if str(lquiz['id']) == sys.argv[5]:
            quiz = lquiz
            break

if quiz == None:
    for index, quiz in enumerate(quizzes):
        print("%2d: %7d - %s" % (index, quiz['id'], quiz['title']))
        
    quiz_index = int(input('Which quiz? '))
    quiz = quizzes[quiz_index]

quiz_id = quiz['id']
print('Using quiz: %s' % (quiz['title']))

# Reading questions
print('Retrieving quiz questions...')
questions = {}
for list in api_request('/courses/%d/quizzes/%d/questions?per_page=100' %
                        (course_id, quiz_id)):
    for question in list:
        if question_included(question['id']):
            questions[question['id']] = question

print('Retrieving quiz submissions...')
for response in api_request('/courses/%d/quizzes/%d/submissions?'
                            'include[]=user&include[]=submission&'
                            'include[]=submission_history'
                            % (course_id, quiz_id), DEBUG):
    quiz_submissions += response['quiz_submissions']
    for student in response['users']:
        students[student['id']] = student
    for submission in response['submissions']:
        submissions[submission['id']] = submission

print('Generating HTML files...')

file_no = 1;
template_file = start_file(exam_name + '_template.html')
exams_file    = start_file(exam_name + '_exams_%d.html' % file_no)
rawanswers_file = zipfile.ZipFile(exam_name + '_raw_answers.zip', 'w')

write_exam_file(template_file, questions)

if DEBUG:
    with open('debug.json', 'w') as file:
        data = {}
        data['quiz'] = quiz
        data['submissions'] = submissions
        data['students'] = students
        data['quiz_submissions'] = quiz_submissions
        data['questions'] = questions
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
        exams_file = start_file(exam_name + '_exams_%d.html' % file_no)

end_file(template_file)
end_file(exams_file)
rawanswers_file.close()

print('\nConverting to PDF...')

for file in htmlfile_list:
    print(file + '...  ', end='\r');
    weasyprint.HTML(filename=file).write_pdf(file + '.pdf')

print('\nDONE. Created files:')
for file in htmlfile_list:
    print('- ' + file + '.pdf')
print('- ' + exam_name + '_raw_answers.zip')
