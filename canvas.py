import requests
import json

MAIN_URL = 'https://canvas.ubc.ca/api/v1'

class Canvas:
    def __init__(self, token):
        self.token = token
        self.token_header = {'Authorization': 'Bearer %s' % token}

    def request(self, request, stopAtFirst = False, debug = False):
        retval = []
        response = requests.get(MAIN_URL + request,
                                headers = self.token_header)
        while True:
            response.raise_for_status()
            if (debug): print(response.text)
            retval.append(response.json())
            if stopAtFirst or 'current' not in response.links or \
               'last' not in response.links or \
               response.links['current']['url'] == response.links['last']['url']:
                break
            response = requests.get(response.links['next']['url'],
                                    headers = self.token_header)
        return retval

    def put(self, url, data):
        response = requests.put(MAIN_URL + url, json = data,
                                headers = self.token_header)
        response.raise_for_status()
        return response.json()

    def post(self, url, data):
        response = requests.post(MAIN_URL + url, json = data,
                                 headers = self.token_header)
        response.raise_for_status()
        return response.json()

    def courses(self):
        courses = []
        for list in self.request('/courses?include[]=term&state[]=available'):
            courses.extend(list)
        return courses

    def course(self, course_id):
        for course in self.request('/courses/%d?include[]=term' % course_id):
            return course
        return None

    def quizzes(self, course):
        quizzes = []
        for list in self.request('/courses/%d/quizzes' % course['id']):
            quizzes += [quiz for quiz in list
                        if quiz['quiz_type'] == 'assignment']
        return quizzes

    def quiz(self, course, quiz_id):
        for quiz in self.request('/courses/%d/quizzes/%d' %
                                 (course['id'], quiz_id)):
            return quiz
        return None

    def update_quiz(self, course, quiz_id, quiz_data):
        if quiz_id:
            return self.put('/courses/%d/quizzes/%d' %
                            (course['id'], quiz_id),
                            { 'quiz': quiz_data } )
        else:
            return self.post('/courses/%d/quizzes' % course['id'],
                            { 'quiz': quiz_data } )

    def question_group(self, course, quiz, group_id):
        if group_id == None: return None
        for group in self.request('/courses/%d/quizzes/%d/groups/%d'
                                  % (course['id'], quiz['id'], group_id)):
            return group
        return None

    # If group_id is None, creates a new one
    def update_question_group(self, course, quiz, group_id, group_data):
        if group_id:
            return self.put('/courses/%d/quizzes/%d/groups/%d' %
                            (course['id'], quiz['id'], group_id),
                            { 'quiz_groups': [group_data] } )
        else:
            return self.post('/courses/%d/quizzes/%d/groups' %
                             (course['id'], quiz['id']),
                             { 'quiz_groups': [group_data] } )
    
    def questions(self, course, quiz, filter=None, include_groups=False):
        questions = {}
        for list in self.request('/courses/%d/quizzes/%d/questions?per_page=100' %
                                 (course['id'], quiz['id'])):
            for question in list:
                if not filter or filter(question['id']):
                    group = self.question_group(course, quiz,
                                                question['quiz_group_id'])
                    if group:
                        question['points_possible'] = group['question_points']
                        if include_groups:
                            question['quiz_group_full'] = group
                    questions[question['id']] = question
        return questions

    def update_question(self, course, quiz, question_id, question_data):
        if question_id:
            return self.put('/courses/%d/quizzes/%d/questions/%d' %
                            (course['id'], quiz['id'], question_id),
                            { 'question': question_data } )
        else:
            return self.post('/courses/%d/quizzes/%d/questions' %
                             (course['id'], quiz['id']),
                             { 'question': question_data } )
    
    def submissions(self, course, quiz, include_user=True,
                    include_submission=True, include_history=True,
                    include_settings_only=False, debug=False):
        submissions = {}
        quiz_submissions = []
        include = ''
        if include_user:       include += 'include[]=user&'
        if include_submission: include += 'include[]=submission&'
        if include_history:    include += 'include[]=submission_history&'
        for response in self.request('/courses/%d/quizzes/%d/submissions?%s'
                                     % (course['id'], quiz['id'], include),
                                     debug):
            quiz_submissions += [qs for qs in response['quiz_submissions']
                                 if include_settings_only or
                                 qs['workflow_state'] != 'settings_only']
            if include_submission:
                for submission in response['submissions']:
                    submissions[submission['id']] = submission
        return (quiz_submissions, submissions)

    def submission_questions(self, quiz_submission):
        questions = {}
        for r in self.request('/quiz_submissions/%d/questions' %
                                  quiz_submission['id']):
            for q in r['quiz_submission_questions']:
                questions[q['id']] = q
        return questions

    def file(self, file_id):
        for file in self.request('/files/%s' % file_id):
            return file

    def send_quiz_grade(self, course, quiz_submission,
                        question_id, points, comments=None):
        self.put('/courses/%d/quizzes/%d/submissions/%d'
                 % (course['id'], quiz_submission['quiz_id'],
                    quiz_submission['id']),
                 {'quiz_submissions': [{
                     'attempt': quiz_submission['attempt'],
                     'questions': { question_id: {'score': points,
                                                  'comment': comments}
                     }
                 }]})

    def assignments(self, course):
        assignments = []
        for list in self.request('/courses/%d/assignments' % course['id']):
            assignments += [a for a in list if
                            'online_quiz' not in a['submission_types']]
        return assignments
        
    def assignment(self, course, assignment_id):
        for assignment in self.request('/courses/%d/assignments/%d' %
                                 (course['id'], assignment_id)):
            return assignment
        return None

    def students(self, course):
        students = {}
        for list in self.request('/courses/%d/users?enrollment_type=student' %
                                 (course['id'])):
            for s in list:
                students[s['sis_user_id'] if s['sis_user_id'] else '0'] = s
        return students

    def rubric(self, course, assignment):

        for r in self.request('/courses/%d/rubrics/%d?include[]=associations' %
                              (course['id'],
                               assignment['rubric_settings']['id'])):
            return r
        return None

    def rubrics(self, course):
        full = []
        for l in self.request('/courses/%d/rubrics?include[]=associations' %
                              (course['id'])):
            full += l
        return full

    def update_rubric(self, course, assignment, rubric):
        data = {
            'rubric': rubric,
            'rubric_association': {
                'association_id': assignment['id'],
                'association_type': 'Assignment',
                'use_for_grading': True,
                'purpose': 'grading',
            },
        }
        self.post('/courses/%d/rubrics' % course['id'], data)

    def send_assig_grade(self, course, assignment, student, assessment):
        self.put('/courses/%d/assignments/%d/submissions/%d' %
                 (course['id'], assignment['id'], student['id']),
                 { 'rubric_assessment': assessment })
