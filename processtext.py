import canvas
import argparse
import re

parser = argparse.ArgumentParser()
canvas.Canvas.add_arguments(parser, quiz=True)

# TODO: help users with creating regular expressions (e.g., have a mode that displays the regexes and takes a test string to act on but doesn't act on Canvas?)
# TODO: modify Canvas so that the file is optional and it will look for a default like token.txt (which should be in .gitignore!) if no argument is given and only then complain
# TODO: arguments for what type(s) of objects to process
# TODO: make optionally interactive with confirmation of changes (via diffing?)
# TODO: reasonable logging
# TODO: need I avoid passing the extra args along to canvas.Canvas?

parser.add_argument("regex", help="")
parser.add_argument("repl", help="The replacement string to use")
args = parser.parse_args()

COMPILED_REGEX = re.compile(args.regex)
REPL = args.repl

canvas = canvas.Canvas(args=args)

print('Reading data from Canvas...')
course = canvas.course(args.course, prompt_if_needed=True)
print('Using course: %s / %s' % (course['term']['name'],
                                 course['course_code']))



# As a first pass, retrieve all the assignments and print their contents.
TARGET_NAME = None
assignments = course.assignments()
assignments1 = assignments[:1]
for assignment in assignments1:
    TARGET_NAME = assignment["name"]
    print("Assignment: %s" % assignment["name"])
    print("--------Body--------")
    print(assignment["description"])
    print("--------------------")

    assignment.data["description"] = COMPILED_REGEX.sub(REPL, assignment.data["description"])
    assignment.update_assignment()

    print("Assignment: %s" % assignment["name"])
    print("--------Body--------")
    print(assignment["description"])
    print("--------------------")


assignments = course.assignments()
for assignment in assignments:
    if assignment["name"] == TARGET_NAME:
        print("Assignment: %s" % assignment["name"])
        print("--------Body--------")
        print(assignment["description"])
        print("--------------------")


# Note: for some reason, Course.assignments filters out "online_quiz" assignment types. Should it?? Are those "Quiz" instead?
