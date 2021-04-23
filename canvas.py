import requests
import json
import argparse
from collections import OrderedDict

MAIN_URL = 'https://canvas.ubc.ca/api/v1'

class Canvas:
    def __init__(self, token = None, args = None):
        if args and args.canvas_token_file:
            token = args.canvas_token_file.read().strip()
            args.canvas_token_file.close()
        elif args and args.canvas_token:
            token = args.canvas_token
        self.token = token
        self.token_header = {'Authorization': 'Bearer %s' % token}

    @staticmethod
    def add_arguments(parser, course=True, quiz=False, assignment=False):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("-f", "--canvas-token-file",
                           type=argparse.FileType('r'),
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
        if response.status_code == 204: return None
        return response.json()

    def post(self, url, data):
        response = requests.post(MAIN_URL + url, json = data,
                                 headers = self.token_header)
        response.raise_for_status()
        if response.status_code == 204: return None
        return response.json()

    def delete(self, url):
        response = requests.delete(MAIN_URL + url, headers = self.token_header)
        response.raise_for_status()
        if response.status_code == 204: return None
        return response.json()

    def courses(self):
        courses = []
        for list in self.request('/courses?include[]=term&state[]=available'):
            courses.extend(list)
        return courses

    def course(self, course_id, prompt_if_needed=False):
        if course_id:
            for course in self.request('/courses/%d?include[]=term' %
                                       course_id):
                return Course(self, course)
        if prompt_if_needed:
                courses = self.courses()
                for index, course in enumerate(courses):
                    print("%2d: %7d - %10s / %s" %
                          (index, course['id'], course.get('term', {}).get('name', 'NO TERM'),
                           course.get('course_code', 'UNKNOWN COURSE')))
                course_index = int(input('Which course? '))
                return Course(self, courses[course_index])
        return None

    def file(self, file_id):
        for file in self.request('/files/%s' % file_id):
            return file
    
class Course(Canvas):
    
    def __init__(self, canvas, course_data):
        super().__init__(canvas.token)
        self.data = course_data
        self.id = course_data['id']
        self.url_prefix = '/courses/%d' % self.id

    def __getitem__(self, index):
        return self.data[index]

    def pages(self):
        pages = []
        for list in self.request('%s/pages' % self.url_prefix):
            # Per https://canvas.instructure.com/doc/api/pages.html#Page,
            # the body is omitted from listing queries. So, we must query
            # individually for each page.
            for page_data in list:
                new_page_datas = self.request('%s/pages/%s' % (self.url_prefix, page_data['url']))
                if len(new_page_datas) == 1:
                    pages.append(Page(self, new_page_datas[0]))
                elif len(new_page_datas) == 0:
                    # Page not found
                    return None
                else:
                    # Too many pages found
                    return None
        return pages

    def quizzes(self):
        quizzes = []
        for list in self.request('%s/quizzes' % self.url_prefix):
            quizzes += [Quiz(self, quiz) for quiz in list
                        if quiz['quiz_type'] == 'assignment']
        return quizzes

    def quiz(self, quiz_id, prompt_if_needed=False):
        if quiz_id:
            for quiz in self.request('%s/quizzes/%d' %
                                     (self.url_prefix, quiz_id)):
                return Quiz(self, quiz)
        if prompt_if_needed:
            quizzes = self.quizzes()
            for index, quiz in enumerate(quizzes):
                print("%2d: %7d - %s" % (index, quiz['id'], quiz['title']))
            quiz_index = int(input('Which quiz? '))
            return quizzes[quiz_index]
        return None
    
    def assignments(self):
        assignments = []
        for list in self.request('%s/assignments' % self.url_prefix):
            assignments += [Assignment(self, a) for a in list if
                            'online_quiz' not in a['submission_types']]
        return assignments
        
    def assignment(self, assignment_id, prompt_if_needed=False):
        if assignment_id:
            for assignment in self.request('%s/assignments/%d' %
                                           (self.url_prefix, assignment_id)):
                return Assignment(self, assignment)
        if prompt_if_needed:
            assignments = self.assignments()
            for index, assignment in enumerate(assignments):
                print("%2d: %7d - %s" % (index, assignment['id'],
                                         assignment['name']))
            asg_index = int(input('Which assignment? '))
            return assignments[asg_index]
        return None

    def rubrics(self):
        full = []
        for l in self.request('%s/rubrics?include[]=associations' %
                              self.url_prefix):
            full += l
        return full
    
    def students(self):
        students = {}
        for list in self.request('%s/users?enrollment_type=student' %
                                 self.url_prefix):
            for s in list:
                students[s['sis_user_id'] if s['sis_user_id'] else '0'] = s
        return students

class CourseSubObject(Canvas):

    # If not provided, the request_param_name defaults to the lower-cased class name.
    def __init__(self, parent, route_name, data, id_field='id', request_param_name=None):
        # MUST be available before calling self.get_course.
        self.parent = parent
        super().__init__(self.get_course().token)

        self.data = data
        self.id_field = id_field
        self.id = self.compute_id()
        self.route_name = route_name
        self.url_prefix = self.compute_url_prefix()
        if not request_param_name:
            request_param_name = type(self).__name__.lower()
        self.request_param_name = request_param_name

    def get_course(self):
        if isinstance(self.parent, Course):
            return self.parent
        else:
            return self.parent.get_course()

    def compute_id(self):
        return self.data[self.id_field]

    def compute_base_url(self):
        return '%s/%s' % (self.parent.url_prefix, self.route_name)
    
    def compute_url_prefix(self):
        return '%s/%s' % (self.compute_base_url(), self.id)

    def __getitem__(self, index):
        return self.data[index]

    def __setitem__(self, index, value):
        self.data[index] = value

    def items(self):
        return self.data.items()

    def update(self, data = None):
        if data:
            self.data = data
        if self.id:
            self.data = self.put(self.url_prefix, { self.request_param_name: self.data } )
        else:
            self.data = self.post(self.compute_base_url(),
                                  { self.route_name: self.data } )
        self.id = self.compute_id()
        self.url_prefix = self.compute_url_prefix()
        return self

class Quiz(CourseSubObject):    
    def __init__(self, course, quiz_data):
        super().__init__(course, "quizzes", quiz_data)

    def update_quiz(self, data=None):
        self.update(data)

    def question_group(self, group_id):
        if group_id == None: return None
        for group in self.request('%s/groups/%d'
                                  % (self.url_prefix, group_id)):
            return group
        return None

    # If group_id is None, creates a new one
    def update_question_group(self, group_id, group_data):
        if group_id:
            return self.put('%s/groups/%d' %
                            (self.url_prefix, group_id),
                            { 'quiz_groups': [group_data] } )
        else:
            return self.post('%s/groups' % self.url_prefix,
                             { 'quiz_groups': [group_data] } )
    
    def questions(self, filter=None):
        questions = {}
        groups = {}
        i = 1
        for list in self.request('%s/questions?per_page=100' %
                                 self.url_prefix):
            for question in list:
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
                if not filter or filter(question['id']):
                    questions[question['id']] = question
        if None in groups: del groups[None]
        for g in groups.values():
            for q in [q for q in questions.values()
                      if q['position'] >= g['position'] and
                      q['quiz_group_id'] is None]:
                q['position'] += 1
        return (OrderedDict(sorted(questions.items(),
                                   key=lambda t:t[1]['position'])),
                OrderedDict(sorted(groups.items(),
                                   key=lambda t:t[1]['position'])))

    def update_question(self, question_id, question):
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
            return self.put('%s/questions/%d' %
                            (self.url_prefix, question_id),
                            { 'question': question } )
        else:
            return self.post('%s/questions' % self.url_prefix,
                             { 'question': question } )
    
    def delete_question(self, question_id):
        return self.delete('%s/questions/%d' %
                           (self.url_prefix, question_id))
    
    def reorder_questions(self, items):
        return self.post('%s/reorder' % self.url_prefix, { 'order': items } )
    
    def submissions(self, include_user=True,
                    include_submission=True, include_history=True,
                    include_settings_only=False, debug=False):
        submissions = {}
        quiz_submissions = []
        include = ''
        if include_user:       include += 'include[]=user&'
        if include_submission: include += 'include[]=submission&'
        if include_history:    include += 'include[]=submission_history&'
        for response in self.request('%s/submissions?%s'
                                     % (self.url_prefix, include), debug):
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

    def send_quiz_grade(self, quiz_submission,
                        question_id, points, comments=None):
        self.put('%s/submissions/%d'
                 % (self.url_prefix, quiz_submission['id']),
                 {'quiz_submissions': [{
                     'attempt': quiz_submission['attempt'],
                     'questions': { question_id: {'score': points,
                                                  'comment': comments}
                     }
                 }]})

class QuizQuestion(CourseSubObject):
    # If the quiz is not supplied, fetches it via quiz_question_data['quiz_id'].
    def __init__(self, quiz_question_data, quiz=None):
        if quiz is None:
            if 'quiz_id' not in quiz_question_data:
                raise RuntimeError('No quiz provided and cannot find quiz id for: %s' % quiz_question_data)
            quiz = course.quiz(quiz_question_data)
        super().__init__(quiz, "quizzes", quiz_question_data, request_param_name='question')

    def update(data = None):
        # Reformat question data to account for different format
        # between input and output in Canvas API
        if 'answers' in data:
            for answer in data['answers']:
                if 'html' in answer:
                    answer['answer_html'] = answer['html']
                if data['question_type'] == 'matching_question':
                    if 'left' in answer:
                        answer['answer_match_left'] = answer['left']
                    if 'right' in answer:
                        answer['answer_match_right'] = answer['right']
                if data['question_type'] == 'multiple_dropdowns_question':
                    if 'weight' in answer:
                        answer['answer_weight'] = answer['weight']
                    if 'text' in answer:
                        answer['answer_text'] = answer['text']

        super.update(data)

    def update_question(self, data=None):
        self.update(data)




class Assignment(CourseSubObject):
    
    def __init__(self, course, assg_data):
        super().__init__(course, "assignments", assg_data)

    def update_assignment(self, data=None):
        self.update(data)

    def rubric(self):
        for r in self.request('%s/rubrics/%d?include[]=associations' %
                              (self.get_course().url_prefix,
                               self.data['rubric_settings']['id'])):
            return r
        return None

    def update_rubric(self, rubric):
        rubric_data = {
            'rubric': rubric,
            'rubric_association': {
                'association_id': self.id,
                'association_type': 'Assignment',
                'use_for_grading': True,
                'purpose': 'grading',
            },
        }
        self.post('%s/rubrics' % self.get_course().url_prefix, rubric_data)

    def send_assig_grade(self, student, assessment):
        self.put('%s/submissions/%d' % (self.url_prefix, student['id']),
                 { 'rubric_assessment': assessment })


class Page(CourseSubObject):
    
    def __init__(self, course, page_data):
        super().__init__(course, "pages", page_data, id_field="url", request_param_name="wiki_page")

    def update_page(self, data=None):
        self.update(self, data)
