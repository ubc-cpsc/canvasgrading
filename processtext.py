import canvas
import argparse
import re
import sys

class BetterErrorParser(argparse.ArgumentParser):
    def error(self, message, help=True):
        sys.stderr.write('error: %s\n' % message)
        if help:
            self.print_help()
        sys.exit(2)


def update_objects(objects, type_name, update_fn):
    print("Processing %s objects" % type_name)
    for obj in objects:
        update_fn(obj)

def make_regex_repl_text_process(regex, repl):
    compiled_regex = re.compile(regex)
    def text_process(text):
        (new_text, count) = compiled_regex.subn(repl, text, count=0)
        return new_text if count > 0 else None
    return text_process

# text_process_fn takes text (as a string) and returns either None if no changes
# are to be made or a new block of text (as a string).
#
# text_fields is either a single string naming a text field to process or a list of
# such strings
#
# title_field is either None (for no title field) or a string naming the title field
# (only for logging). A field can be both title_field and one of the text_fields.
def make_update_text(text_process_fn, text_fields, title_field=None):
    text_fields = text_fields[:] if isinstance(text_fields, list) else[text_fields]
    def update_text(obj):
        print()
        print("---------------------------------------------------------------")
        if title_field:
            print("Processing object: %s" % obj[title_field])
        else:
            print("Processing next object")
        
        for text_field in text_fields:
            update_needed = False

            print("Processing text field: %s" % text_field)
            old_value = obj[text_field]
            new_value = text_process_fn(old_value)
            if new_value is None:
                print("No changes made.")
            else:
                update_needed = True
                obj[text_field] = new_value
                print("Changes made.")
                print("Old value:")
                print(old_value)
                print()
                print()
                print("New value:")
                print(new_value)
                print()
                print()
        
        if update_needed:
            print("Making update on Canvas...")
            obj.update()
            print("Update complete.")

        if title_field:
            print("Done processing object: %s" % obj[title_field])
        else:
            print("Done processing object")
    return update_text

parser = BetterErrorParser()
canvas.Canvas.add_arguments(parser)

# TODO: help users with creating regular expressions (e.g., have a mode that displays the regexes and takes a test string to act on but doesn't act on Canvas?)
# TODO: modify Canvas so that the file is optional and it will look for a default like token.txt (which should be in .gitignore!) if no argument is given and only then complain
# TODO: make optionally interactive with confirmation of changes (via diffing?)
# TODO: reasonable logging
# TODO: need I avoid passing the extra args along to canvas.Canvas?


parser.add_argument("-a", "--assignments", help="Process assignments.", action="store_true")
parser.add_argument("-p", "--pages", help="Process pages.", action="store_true")
parser.add_argument("-q", "--quizzes", help="Process quizzes.", action="store_true")
parser.add_argument("-A", "--all", help="Process all types (assignments, pages, and quizzes).", action="store_true")
parser.add_argument("regex", help="The regular expression (using Python's re syntax) to search for.")
parser.add_argument("repl", help="The replacement string (using Python's syntax from re.sub) with which to replace regex.")
args = parser.parse_args()

regex = args.regex
repl = args.repl

process_assns = args.assignments or args.all
process_quizzes = args.quizzes or args.all
process_pages = args.pages or args.all
if not (process_assns or process_pages or process_quizzes):
    parser.error("You must use a flag to indicate processing of at least one type.")

std_text_process = make_regex_repl_text_process(regex, repl)
update_assn_fn = make_update_text(std_text_process, "description", "name")
update_page_fn = make_update_text(std_text_process, "body", "url")

# TODO: replace std_text_process with one that also accesses the questions (and answers?)
# and updates them.
update_quiz_fn = make_update_text(std_text_process, "description", "title")


canvas = canvas.Canvas(args=args)

print('Object types being processed: %s%s%s' % \
    ("assignments " if process_assns else "",
    "pages " if process_pages else "",
    "quizzes " if process_quizzes else ""))


print('Reading data from Canvas...')
course = canvas.course(args.course, prompt_if_needed=True)
print('Using course: %s / %s' % (course['term']['name'],
                                 course['course_code']))


if process_assns:
    print("Fetching assignments from Canvas...")
    assignments = course.assignments()
    print("Done fetching assignments from Canvas.")
    update_objects(assignments, "assignment", update_assn_fn)

if process_pages:
    print("Fetching pages from Canvas...")
    pages = course.pages()
    print("Done fetching pages from Canvas.")
    update_objects(pages, "page", update_page_fn)

if process_quizzes:
    print("Fetching quizzes from Canvas...")
    quizzes = course.quizzes()
    print("Done fetching quizzes from Canvas.")
    update_objects(quizzes, "quiz", update_quiz_fn)



# Note: for some reason, Course.assignments filters out "online_quiz" assignment types. Should it?? Are those "Quiz" instead?
