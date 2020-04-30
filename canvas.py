import requests

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
        return quizzes

    def question_group(self, course, quiz, group_id):
        if group_id == None: return None
        for group in self.request('/courses/%d/quizzes/%d/groups/%d'
                                  % (course['id'], quiz['id'], group_id)):
            return group
        return None

    def questions(self, course, quiz, filter=None):
        questions = {}
        for list in self.request('/courses/%d/quizzes/%d/questions?per_page=100' %
                                 (course['id'], quiz['id'])):
            for question in list:
                if not filter or filter(question['id']):
                    group = self.question_group(course, quiz,
                                                question['quiz_group_id'])
                    if group:
                        question['points_possible'] = group['question_points']
                    questions[question['id']] = question
        return questions

    def submissions(self, course, quiz, include_user=True,
                    include_submission=True, include_history=True,
                    debug=False):
        submissions = {}
        quiz_submissions = []
        include = ''
        if include_user:       include += 'include[]=user&'
        if include_submission: include += 'include[]=submission&'
        if include_history:    include += 'include[]=submission_history&'
        for response in self.request('/courses/%d/quizzes/%d/submissions?%s'
                                     % (course['id'], quiz['id'], include),
                                     debug):
            quiz_submissions += response['quiz_submissions']
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
