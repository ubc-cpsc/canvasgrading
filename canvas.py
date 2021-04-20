import argparse
from collections import OrderedDict
import requests

MAIN_URL = 'https://canvas.ubc.ca/api/v1'

class Canvas:
    """ Canvas """
    def __init__(self, token=None, args=None):
        self.debug = args.debug if args else False
        if args and args.canvas_token_file:
            token = args.canvas_token_file.read().strip()
            args.canvas_token_file.close()
        elif args and args.canvas_token:
            token = args.canvas_token
        self.token = token
        self.token_header = {'Authorization': f'Bearer {token}'}

    @staticmethod
    def add_arguments(parser, course=True, quiz=False, assignment=False):
        """ docstring """
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("-f", "--canvas-token-file", type=argparse.FileType('r'),
                           help="File containing the Canvas token used for authentication")
        group.add_argument("-t", "--canvas-token",
                           help="Canvas token used for authentication")
        if course:
            parser.add_argument("-c", "--course", type=int,
                                help="Course ID")
        if quiz:
            parser.add_argument("-q", "--quiz", type=int,
                                help="Quiz ID")
        if assignment:
            parser.add_argument("-a", "--assignment", type=int,
                                help="Assignment ID")


    def request(self, request, stop_at_first=False):
        """ docstring """
        retval = []
        response = requests.get(MAIN_URL + request, headers=self.token_header)
        while True:
            response.raise_for_status()
            if self.debug:
                print(response.text)
            retval.append(response.json())
            if (stop_at_first or
                    'current' not in response.links or
                    'last' not in response.links or
                    response.links['current']['url'] == response.links['last']['url']):
                break
            response = requests.get(response.links['next']['url'], headers=self.token_header)
        return retval

    def put(self, url, data):
        """ docstring """
        response = requests.put(MAIN_URL + url, json=data, headers=self.token_header)
        response.raise_for_status()
        if response.status_code == 204:
            return None
        return response.json()

    def post(self, url, data):
        """ docstring """
        response = requests.post(MAIN_URL + url, json=data, headers=self.token_header)
        response.raise_for_status()
        if response.status_code == 204:
            return None
        return response.json()

    def delete(self, url):
        """ docstring """
        response = requests.delete(MAIN_URL + url, headers=self.token_header)
        response.raise_for_status()
        if response.status_code == 204:
            return None
        return response.json()

    def courses(self):
        """ docstring """
        courses = []
        for result in self.request('/courses?include[]=term&state[]=available'):
            courses.extend(result)
        return courses

    def course(self, course_id, prompt_if_needed=False):
        """ docstring """
        if course_id:
            for course in self.request(f'/courses/{course_id}?include[]=term'):
                return Course(self, course)
        if prompt_if_needed:
            courses = self.courses()
            for index, course in enumerate(courses):
                term = course.get('term', {}).get('name', 'NO TERM')
                course_code = course.get('course_code', 'UNKNOWN COURSE')
                print(f"{index:2}: {course['id']:7} - {term:10} / {course_code}")
            course_index = int(input('Which course? '))
            return Course(self, courses[course_index])
        return None

    def file(self, file_id):
        """ docstring """
        for file in self.request(f'/files/{file_id}'):
            return file

class Course(Canvas):
    """ Course """

    def __init__(self, canvas, course_data):
        super().__init__(canvas.token)
        self.data = course_data
        self.id = course_data['id']
        self.url_prefix = '/courses/%d' % self.id

    def __getitem__(self, index):
        return self.data[index]

    def quizzes(self):
        """ docstring """
        quizzes = []
        for result in self.request(f'{self.url_prefix}/quizzes'):
            quizzes += [Quiz(self, quiz) for quiz in result if quiz['quiz_type'] == 'assignment']
        return quizzes

    def quiz(self, quiz_id, prompt_if_needed=False):
        """ docstring """
        if quiz_id:
            for quiz in self.request(f'{self.url_prefix}/quizzes/{quiz_id}'):
                return Quiz(self, quiz)
        if prompt_if_needed:
            quizzes = self.quizzes()
            for index, quiz in enumerate(quizzes):
                print(f"{index:2}: {quiz['id']:7} - {quiz['title']}")
            quiz_index = int(input('Which quiz? '))
            return quizzes[quiz_index]
        return None

    def assignments(self):
        """ docstring """
        assignments = []
        for result in self.request(f'{self.url_prefix}/assignments'):
            assignments += [Assignment(self, assn) for assn in result if 'online_quiz' not in assn['submission_types']]
        return assignments

    def assignment(self, assignment_id, prompt_if_needed=False):
        """ docstring """
        if assignment_id:
            for assignment in self.request(f'{self.url_prefix}/assignments/{assignment_id}'):
                return Assignment(self, assignment)
        if prompt_if_needed:
            assignments = self.assignments()
            for index, assignment in enumerate(assignments):
                print(f"{index:2}: {assignment['id']:7} - {assignment['name']}")
            asg_index = int(input('Which assignment? '))
            return assignments[asg_index]
        return None

    def rubrics(self):
        """ docstring """
        full = []
        for result in self.request(f'{self.url_prefix}/rubrics?include[]=associations'):
            full += result
        return full

    def students(self):
        """ docstring """
        students = {}
        for result in self.request(f'{self.url_prefix}/users?enrollment_type=student'):
            for student in result:
                sis_user_id = student['sis_user_id'] if student['sis_user_id'] else '0'
                students[sis_user_id] = student
        return students

class Quiz(Canvas):
    """ Quiz """

    def __init__(self, course, quiz_data):
        super().__init__(course.token)
        self.course = course
        self.data = quiz_data
        self.id = quiz_data['id']
        self.url_prefix = f'{course.url_prefix}/quizzes/{self.id}'

    def __getitem__(self, index):
        return self.data[index]

    def __setitem__(self, index, value):
        self.data[index] = value

    def items(self):
        """ docstring """
        return self.data.items()

    def update_quiz(self, data=None):
        """ docstring """
        if data:
            self.data = data
        if self.id:
            self.data = self.put(self.url_prefix, {'quiz': self.data})
        else:
            self.data = self.post(f'{self.course.url_prefix}/quizzes', {'quiz': self.data})
        self.id = self.data['id']
        self.url_prefix = f'{self.course.url_prefix}/quizzes/{self.id}'
        return self

    def question_group(self, group_id):
        """ docstring """
        if group_id is None:
            return None
        for group in self.request(f'{self.url_prefix}/groups/{group_id}'):
            return group
        return None

    # If group_id is None, creates a new one
    def update_question_group(self, group_id, group_data):
        """ docstring """
        if group_id:
            return self.put(f'{self.url_prefix}/groups/{group_id}', {'quiz_groups': [group_data]})
        return self.post(f'{self.url_prefix}/groups', {'quiz_groups': [group_data]})

    def questions(self, qfilter=None):
        """ docstring """
        questions = {}
        groups = {}
        i = 1
        for result in self.request(f'{self.url_prefix}/questions?per_page=100'):
            for question in result:
                if question['quiz_group_id'] in groups:
                    group = groups[question['quiz_group_id']]
                else:
                    group = self.question_group(question['quiz_group_id'])
                    groups[question['quiz_group_id']] = group

                if group:
                    question['points_possible'] = group['question_points']
                    question['position'] = group['position']
                else:
                    question['position'] = i
                    i += 1
                if not qfilter or qfilter(question['id']):
                    questions[question['id']] = question
        if None in groups:
            del groups[None]
        for grp in groups.values():
            for question in [
                    q for q in questions.values() if q['position'] >= grp['position'] and q['quiz_group_id'] is None]:
                question['position'] += 1
        return (OrderedDict(sorted(questions.items(), key=lambda t: t[1]['position'])),
                OrderedDict(sorted(groups.items(), key=lambda t: t[1]['position'])))

    def update_question(self, question_id, question):
        """ docstring """
        # Reformat question data to account for different format
        # between input and output in Canvas API
        if 'answers' in question:
            for answer in question['answers']:
                if 'html' in answer:
                    answer['answer_html'] = answer['html']
                if question['question_type'] == 'matching_question':
                    if 'left' in answer:
                        answer['answer_match_left'] = answer['left']
                    if 'right' in answer:
                        answer['answer_match_right'] = answer['right']
                if question['question_type'] == 'multiple_dropdowns_question':
                    if 'weight' in answer:
                        answer['answer_weight'] = answer['weight']
                    if 'text' in answer:
                        answer['answer_text'] = answer['text']
        # Update
        if question_id:
            return self.put(f'{self.url_prefix}/questions/{question_id}', {'question': question})
        return self.post(f'{self.url_prefix}/questions', {'question': question})

    def delete_question(self, question_id):
        """ docstring """
        return self.delete(f'{self.url_prefix}/questions/{question_id}')

    def reorder_questions(self, items):
        """ docstring """
        return self.post(f'{self.url_prefix}/reorder', {'order': items})

    def submissions(self, include_user=True,
                    include_submission=True, include_history=True,
                    include_settings_only=False):
        """ docstring """
        submissions = {}
        quiz_submissions = []
        include = ''.join([
            'include[]=user&' if include_user else '',
            'include[]=submission&' if include_submission else '',
            'include[]=submission_history&' if include_history else '',
            ])
        for response in self.request(f'{self.url_prefix}/submissions?{include}'):
            quiz_submissions += [
                qs for qs in response['quiz_submissions']
                if include_settings_only or qs['workflow_state'] != 'settings_only'
                ]
            if include_submission:
                for submission in response['submissions']:
                    submissions[submission['id']] = submission
        return (quiz_submissions, submissions)

    def submission_questions(self, quiz_submission):
        """ docstring """
        questions = {}
        for result in self.request(f"/quiz_submissions/{quiz_submission['id']}/questions"):
            for question in result['quiz_submission_questions']:
                questions[question['id']] = question
        return questions

    def send_quiz_grade(self, quiz_submission,
                        question_id, points, comments=None):
        """ docstring """
        self.put(f"{self.url_prefix}/submissions/{quiz_submission['id']}",
                 {'quiz_submissions': [{
                     'attempt': quiz_submission['attempt'],
                     'questions': {question_id: {'score': points, 'comment': comments}}
                 }]})

class Assignment(Canvas):
    """ Assignment """

    def __init__(self, course, assg_data):
        super().__init__(course.token)
        self.course = course
        self.data = assg_data
        self.id = assg_data['id']
        self.url_prefix = f'{course.url_prefix}/assignments/{self.id}'

    def __getitem__(self, index):
        return self.data[index]

    def rubric(self):
        """ docstring """
        for result in self.request(
                f"{self.course.url_prefix}/rubrics/{self.data['rubric_settings']['id']}?include[]=associations"):
            return result
        return None

    def update_rubric(self, rubric):
        """ docstring """
        rubric_data = {
            'rubric': rubric,
            'rubric_association': {
                'association_id': self.id,
                'association_type': 'Assignment',
                'use_for_grading': True,
                'purpose': 'grading',
            },
        }
        self.post(f'{self.course.url_prefix}/rubrics', rubric_data)

    def send_assig_grade(self, student, assessment):
        """ docstring """
        self.put(f"{self.url_prefix}/submissions/{student['id']}", {'rubric_assessment': assessment})
